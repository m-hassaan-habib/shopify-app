from flask import Blueprint, render_template, request, jsonify, redirect, flash, url_for
from models.db import get_connection
from werkzeug.utils import secure_filename
import csv, os, datetime
from logger import get_logger
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor
from selenium.webdriver.common.keys import Keys

import traceback
import time
import tempfile
import random
import json


logger = get_logger("routes")


routes = Blueprint("routes", __name__)


def load_templates():
    conn = get_connection()
    with conn.cursor() as c:
        c.execute("SELECT template_name, content FROM message_templates")
        rows = c.fetchall()
    return {r["template_name"]: json.loads(r["content"]) for r in rows}


def build_message(name, product, order_num, price, templates):
    return (
        f"{random.choice(templates['greetings'])}, *{name or 'Customer'}*,\n\n"
        f"{random.choice(templates['intros'])}\n\n"
        f"{random.choice(templates['order_lines']).format(product=product, order_num=order_num, price=price)}\n\n"
        f"{random.choice(templates['confirmation_requests'])}\n\n"
        f"{random.choice(templates['closings'])}"
    )


def human_delay(base=5, variation=3):
    time.sleep(base + random.uniform(0, variation))


def safe_float(value, fallback=0.0):
    try:
        return float(value)
    except Exception as e:
        if str(value).strip():  # don't log if it's just empty
            logger.warning(f"Failed float cast: {value} → {e}")
        return fallback


def parse_date(val):
    val = str(val).strip()
    if not val:
        return datetime.datetime.now()  # Don’t warn for blanks

    for fmt in ['%Y-%m-%d %H:%M:%S %z', '%m/%d/%Y']:
        try:
            return datetime.datetime.strptime(val, fmt)
        except:
            continue

    logger.warning(f"Unrecognized date format: '{val}'")
    return datetime.datetime.now()


@routes.route('/orders/status/<status>')
def filtered_orders(status):
    conn = get_connection()
    with conn.cursor() as cursor:
        if status == 'total':
            cursor.execute("SELECT * FROM orders ORDER BY id DESC")
        else:
            cursor.execute("SELECT * FROM orders WHERE status = %s ORDER BY id DESC", (status,))
        orders = cursor.fetchall()
    return render_template("orders.html", orders=orders, current_filter=status)


@routes.route('/')
def dashboard():
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS total FROM orders")
        total_orders = cursor.fetchone()['total']

        cursor.execute("SELECT COUNT(*) AS confirmed FROM orders WHERE status = 'Confirmd'")
        confirmed_orders = cursor.fetchone()['confirmed']

        cursor.execute("SELECT COUNT(*) AS cancelled FROM orders WHERE status = 'Cancelled'")
        cancelled_orders = cursor.fetchone()['cancelled']

        cursor.execute("SELECT COUNT(*) AS pending FROM orders WHERE status = 'Pending'")
        pending_orders = cursor.fetchone()['pending']

        cursor.execute("SELECT COUNT(*) AS not_responding FROM orders WHERE status = 'Not Responding'")
        not_responding_orders = cursor.fetchone()['not_responding']

        cursor.execute("SELECT COUNT(*) AS to_process FROM orders WHERE status = 'To Process'")
        to_process_orders = cursor.fetchone()['to_process']

        cursor.execute("""
            SELECT item_name, COUNT(*) as count
            FROM orders GROUP BY item_name ORDER BY count DESC LIMIT 5
        """)
        top_products = cursor.fetchall()
        top_products_labels = [r['item_name'] for r in top_products]
        top_products_counts = [r['count'] for r in top_products]

        cursor.execute("""
            SELECT billing_city, COUNT(*) as count
            FROM orders GROUP BY billing_city ORDER BY count DESC LIMIT 5
        """)
        cities = cursor.fetchall()
        city_labels = [r['billing_city'] for r in cities]
        city_counts = [r['count'] for r in cities]

    return render_template("dashboard.html",
        total_orders=total_orders,
        confirmed_orders=confirmed_orders,
        cancelled_orders=cancelled_orders,
        pending_orders=pending_orders,
        not_responding_orders=not_responding_orders,
        to_process_orders=to_process_orders,
        top_products_labels=top_products_labels,
        top_products_counts=top_products_counts,
        city_labels=city_labels,
        city_counts=city_counts
    )


@routes.route('/orders')
def orders():
    return render_template("orders.html")

@routes.route('/order/<int:order_id>', methods=['GET'])
def get_order(order_id):
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM orders WHERE id = %s", (order_id,))
        order = cursor.fetchone()
    return jsonify(order)

@routes.route('/order/<int:order_id>', methods=['PUT'])
def update_order(order_id):
    data = request.json
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE orders SET
                order_source=%s, order_number=%s, subtotal=%s, shipping=%s, total=%s,
                discount_code=%s, discount_amount=%s, created_at=%s,
                quantity=%s, item_name=%s, billing_name=%s, billing_phone=%s,
                billing_street=%s, billing_city=%s, status=%s,
                advance_delivery_charges=%s, cod_amount=%s, courier=%s, shipping_status=%s
            WHERE id = %s
        """, (
            data["order_source"], data["order_number"], data["subtotal"], data["shipping"],
            float(data["subtotal"]) + float(data["shipping"]),
            data["discount_code"], data["discount_amount"],
            data["created_at"], data["quantity"], data["item_name"],
            data["billing_name"], data["billing_phone"], data["billing_street"],
            data["billing_city"], data["status"], data["advance_delivery_charges"],
            data["cod_amount"], data["courier"], data["shipping_status"],
            order_id
        ))
        conn.commit()
    return jsonify({"status": "updated"})

@routes.route('/order/<int:order_id>/status', methods=['PATCH'])
def update_order_status(order_id):
    try:
        status = request.json.get("status")
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE orders SET status = %s WHERE id = %s", (status, order_id))
            conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@routes.route('/order/<int:order_id>', methods=['DELETE'])
def delete_order(order_id):
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM orders WHERE id = %s", (order_id,))
        conn.commit()
    return jsonify({"status": "deleted"})


@routes.route('/order', methods=['POST'])
def create_order():
    data = request.json
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO orders (order_source, order_number, subtotal, shipping, total, discount_code,
            discount_amount, created_at, quantity, item_name, billing_name, billing_phone,
            billing_street, billing_city, status, advance_delivery_charges, cod_amount, courier, shipping_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data["order_source"], data["order_number"], data["subtotal"], data["shipping"],
            float(data["subtotal"]) + float(data["shipping"]),
            data["discount_code"], data["discount_amount"],
            data["created_at"], data["quantity"], data["item_name"],
            data["billing_name"], data["billing_phone"], data["billing_street"],
            data["billing_city"], data["status"], data["advance_delivery_charges"],
            data["cod_amount"], data["courier"], data["shipping_status"]
        ))
        conn.commit()
    return jsonify({"status": "success"})


@routes.route('/import', methods=['POST'])
def import_csv():
    try:
        logger.info("IMPORT ROUTE HIT")
        file = request.files['file']
        filename = secure_filename(file.filename)

        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        flash(f"CSV uploaded successfully: {filename}", "info")
        logger.info(f"File uploaded: {filepath}")

        conn = get_connection()
        rows = []

        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for idx, row in enumerate(reader, start=1):
                try:
                    created_at = parse_date(row['Created at'])
                except Exception as err:
                    flash(f"Row {idx} date parsing failed: {row['Created at']} → {err}", "warning")
                    logger.warning(f"Row {idx} datetime parse failed: {err}")
                    created_at = datetime.datetime.now()

                record = (
                    row.get('Order placed', 'Shopify'),
                    row.get('Order #', '').strip(),
                    safe_float(row.get('Subtotal')),
                    safe_float(row.get('Shipping')),
                    safe_float(row.get('Subtotal')) + safe_float(row.get('Shipping')),
                    row.get('Discount Code', '').strip(),
                    safe_float(row.get('Discount Amount')),
                    created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    int(row.get('Lineitem quantity') or 1),
                    row.get('Lineitem name', '').strip(),
                    row.get('Billing Name', '').strip(),
                    row.get('Billing Phone', '').strip(),
                    row.get('Billing Street', '').strip(),
                    row.get('Billing City', '').strip(),
                    row.get('Status', '').strip(),
                    row.get('Advance Delivery Charges', '').strip(),
                    safe_float(row.get('COD Amount')),
                    row.get('Courier', '').strip(),
                    row.get('Shipping Status', '').strip()
                )


                if len(record) != 19:
                    logger.error(f"Skipping malformed row {idx} with {len(record)} fields: {record}")
                    flash(f"Skipping malformed row {idx} — field count is off", "danger")
                    continue

                rows.append(record)

        logger.info(f"Parsed {len(rows)} valid rows from CSV")
        flash(f"Parsed {len(rows)} valid rows from CSV", "info")

        if rows:
            with conn.cursor() as cursor:
                cursor.executemany("""
                    INSERT INTO orders (
                        order_source, order_number, subtotal, shipping, total,
                        discount_code, discount_amount, created_at, quantity, item_name,
                        billing_name, billing_phone, billing_street, billing_city, status,
                        advance_delivery_charges, cod_amount, courier, shipping_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, rows)
                conn.commit()
            flash("All rows inserted successfully", "success")
            logger.info(f"{len(rows)} rows inserted into DB")
        else:
            flash("No valid rows to insert", "danger")
            logger.warning("No valid rows found in CSV")

    except Exception as e:
        flash(f"Fatal error: {str(e)}", "danger")
        logger.exception("Error while importing CSV")

    return redirect(url_for('routes.orders'))


@routes.route('/get_orders', methods=['GET'])
def get_all_orders():
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM orders ORDER BY id DESC")
            orders = cursor.fetchall()
        return jsonify(orders)
    except Exception as e:
        logger.exception("Failed to fetch orders")
        flash("Failed to load orders", "danger")
        return jsonify([]), 500


@routes.route('/support')
def support():
    return render_template("customer_support.html")


@routes.route('/delivery')
def delivery():
    return render_template("delivery_support.html")

@routes.route('/order/<int:order_id>/shipping_status', methods=['PATCH'])
def update_shipping_status(order_id):
    data = request.get_json()
    new_status = data.get('shipping_status')

    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE orders SET shipping_status = %s WHERE id = %s
        """, (new_status, order_id))
        conn.commit()

    return jsonify({"status": "updated"})


@routes.route('/order/<int:order_id>/courier', methods=['PATCH'])
def update_courier(order_id):
    data = request.get_json()
    new_status = data.get('courier')

    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE orders SET courier = %s WHERE id = %s
        """, (new_status, order_id))
        conn.commit()

    return jsonify({"status": "updated"})


@routes.route('/send_whatsapp', methods=['POST'])
def send_whatsapp():
    failed_numbers = []
    conn = get_connection()
    headless_mode = request.form.get("headless") is not None

    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT order_number, billing_name, item_name, billing_phone, total "
            "FROM orders WHERE status IN ('To Process', 'Not Responding')"
        )
        users = cursor.fetchall()
    try:
        options = Options()
        options.add_argument('--user-data-dir=./whatsapp_session')
        options.add_argument('--window-size=1920,1080')
        if headless_mode:
            options.add_argument('--headless=new')
            
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get('https://web.whatsapp.com')
        time.sleep(15)
        batch_size = 2

        def send_in_tab(index, user):
            templates = load_templates()
    
            greetings = templates["greetings"]
            intros = templates["intros"]
            order_lines = templates["order_lines"]
            confirmation_requests = templates["confirmation_requests"]
            closings = templates["closings"]
            
            name    = user['billing_name'] or 'Customer'
            product = user['item_name'] or 'your product'
            phone   = user['billing_phone']
            o_num   = user['order_number']
            price   = user['total']
            message = build_message(name, product, o_num, price, templates)
            link    = f"https://web.whatsapp.com/send?phone={phone}"

            driver.execute_script(f"window.open('{link}','_blank');")
            human_delay(2,1)
            driver.switch_to.window(driver.window_handles[-1])
            human_delay(10,5)

            try:
                xpath = '//div[@contenteditable="true" and @data-tab="10"]'
                box   = WebDriverWait(driver,15).until(EC.presence_of_element_located((By.XPATH, xpath)))
                box.click(); human_delay(1,1)
                box.clear()

                parts = message.split("\n\n")

                msg1 = f"{parts[0].strip()} {parts[1].strip()}" if len(parts) > 1 else parts[0].strip()

                msg2 = " ".join(p.strip() for p in parts[2:])

                box.send_keys(msg1)
                box.send_keys(Keys.ENTER)
                human_delay(1,1)

                if msg2:
                    box.send_keys(msg2)
                    box.send_keys(Keys.ENTER)
                    human_delay(1,1)

                with get_connection().cursor() as c2:
                    c2.execute("UPDATE orders SET status='Confirmd' WHERE order_number=%s", (o_num,))
                    c2.connection.commit()

                logger.info(f"Sent message to {phone}")

            except Exception as e:
                failed_numbers.append(phone)
                logger.error(f"Send failed for {phone}: {e}")

            human_delay(5,3)
            driver.close()
            human_delay(1,1)
            driver.switch_to.window(driver.window_handles[0])

        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[0])
        driver.get('https://web.whatsapp.com')
        time.sleep(10)
        for i in range(0, len(users), batch_size):
            batch = users[i:i + batch_size]
            for idx, user in enumerate(batch):
                send_in_tab(idx, user)
        driver.quit()
        return jsonify({'message': f'{len(users)} messages processed', 'failed_numbers': failed_numbers})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@routes.route('/orders/confirm_all', methods=['POST'])
def confirm_all_orders():
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE orders 
                SET status = 'Confirmd' 
                WHERE status IN ('To Process', 'Not Responding')
            """)
            conn.commit()
        flash("Yesterday orders marked as Confirmed", "success")
    except Exception as e:
        logger.exception("Bulk confirm failed")
        flash(f"Error confirming orders: {str(e)}", "danger")

    return redirect(url_for("routes.dashboard", status="total"))


def send_multiline_message(msg_box, message):
    for line in message.split("\n"):
        if line.strip():
            msg_box.send_keys(line.strip())
            msg_box.send_keys(Keys.ENTER)
            human_delay(0.5, 0.5)


@routes.route('/orders/delete_all', methods=['POST'])
def delete_all_orders():
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM orders")
            conn.commit()
        flash("All orders deleted successfully", "warning")
    except Exception as e:
        logger.exception("Bulk delete failed")
        flash(f"Error deleting orders: {str(e)}", "danger")

    return redirect(url_for("routes.dashboard", status="total"))


@routes.route('/templates')
def list_templates():
    conn = get_connection()
    with conn.cursor() as c:
        c.execute("SELECT * FROM message_templates")
        tpl = c.fetchall()
    return render_template('templates.html', templates=tpl)


@routes.route('/templates/<int:tpl_id>', methods=['GET','POST'])
def edit_template(tpl_id):
    conn = get_connection()
    if request.method == 'POST':
        new_items = request.form.getlist('items')
        new_content = json.dumps(new_items)
        with conn.cursor() as c:
            c.execute("UPDATE message_templates SET content=%s WHERE id=%s", (new_content, tpl_id))
            conn.commit()
        flash("Template updated", "success")
        return redirect(url_for('routes.list_templates'))
    with conn.cursor() as c:
        c.execute("SELECT * FROM message_templates WHERE id=%s", (tpl_id,))
        tpl = c.fetchone()
        items = json.loads(tpl["content"])
    return render_template('edit_template.html', template=tpl, items=items)


