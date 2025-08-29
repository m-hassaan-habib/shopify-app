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

def build_message(name, product, order_num, price, tracking, templates, message_type='confirmation'):
    if message_type == 'confirmation':
        return (
            f"{random.choice(templates.get('greetings', ['Hi']))}, *{name or 'Customer'}*,\n\n"
            f"{random.choice(templates.get('intros', ['Thank you for your order']))}\n\n"
            f"{random.choice(templates.get('order_lines', ['Your order: {product}'])).format(product=product, order_num=order_num, price=price)}\n\n"
            f"{random.choice(templates.get('confirmation_requests', ['Please confirm']))}\n\n"
            f"{random.choice(templates.get('closings', ['Best regards']))}"
        )
    elif message_type == 'return':
        return (
            f"{random.choice(templates.get('return_greetings', ['Hi']))}, *{name or 'Customer'}*,\n\n"
            f"{random.choice(templates.get('return_intros', ['Your order was returned']))}\n\n"
            f"{random.choice(templates.get('return_order_lines', ['Order: {product}'])).format(product=product, order_num=order_num, price=price)}\n\n"
            f"{random.choice(templates.get('return_requests', ['Do you still need it? We can resend via another courier']))}\n\n"
            f"{random.choice(templates.get('return_closings', ['Let us know']))}"
        )
    elif message_type == 'cancelled':
        return (
            f"{random.choice(templates.get('cancelled_greetings', ['Hi']))}, *{name or 'Customer'}*,\n\n"
            f"{random.choice(templates.get('cancelled_intros', ['We noticed your order was cancelled']))}\n\n"
            f"{random.choice(templates.get('cancelled_order_lines', ['But we have new products']))}\n\n"
            f"{random.choice(templates.get('cancelled_requests', ['Are you interested?']))}\n\n"
            f"{random.choice(templates.get('cancelled_closings', ['Check our range']))}"
        )
    elif message_type == 'valued':
        return (
            f"{random.choice(templates.get('valued_greetings', ['Hi valued customer']))}, *{name or 'Customer'}*,\n\n"
            f"{random.choice(templates.get('valued_intros', ['Thanks for your past orders']))}\n\n"
            f"{random.choice(templates.get('valued_order_lines', ['Check our latest products and bundles']))}\n\n"
            f"{random.choice(templates.get('valued_requests', ['Special offers for you']))}\n\n"
            f"{random.choice(templates.get('valued_closings', ['Shop now']))}"
        )
    elif message_type == 'tracking':
        return (
            f"{random.choice(templates.get('tracking_greetings', ['Hi']))}, *{name or 'Customer'}*,\n\n"
            f"{random.choice(templates.get('tracking_intros', ['Your order is on the way']))}\n\n"
            f"{random.choice(templates.get('tracking_order_lines', ['Track your parcel']))}\n\n"
            f"Tracking number: {tracking}\n\n"
            f"{random.choice(templates.get('tracking_closings', ['Happy shopping']))}"
        )

def human_delay(base=5, variation=3):
    time.sleep(base + random.uniform(0, variation))

def safe_float(value, fallback=0.0):
    try:
        return float(value)
    except Exception as e:
        if str(value).strip():
            logger.warning(f"Failed float cast: {value} → {e}")
        return fallback

def parse_date(val):
    val = str(val).strip()
    if not val:
        return datetime.datetime.now()
    for fmt in ['%Y-%m-%d %H:%M:%S %z', '%m/%d/%Y']:
        try:
            return datetime.datetime.strptime(val, fmt)
        except:
            continue
    logger.warning(f"Unrecognized date format: '{val}'")
    return datetime.datetime.now()

@routes.route('/orders/status/<status>')
def filtered_orders(status):
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_connection()
    with conn.cursor() as cursor:
        if status == 'total':
            cursor.execute("SELECT COUNT(*) AS cnt FROM orders")
            total_orders = cursor.fetchone()['cnt']
            cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT %s OFFSET %s", (per_page, offset))
        elif status == 'Valued':
            cursor.execute("SELECT COUNT(*) AS cnt FROM orders WHERE customer_type = %s", (status,))
            total_orders = cursor.fetchone()['cnt']
            cursor.execute("SELECT * FROM orders WHERE customer_type = %s ORDER BY id DESC LIMIT %s OFFSET %s",
                           (status, per_page, offset))
        else:
            cursor.execute("SELECT COUNT(*) AS cnt FROM orders WHERE status = %s OR shipping_status = %s", (status, status))
            total_orders = cursor.fetchone()['cnt']
            cursor.execute("SELECT * FROM orders WHERE status = %s OR shipping_status = %s ORDER BY id DESC LIMIT %s OFFSET %s",
                           (status, status, per_page, offset))

        orders = cursor.fetchall()

    total_pages = (total_orders + per_page - 1) // per_page

    return render_template(
        "orders.html",
        orders=orders,
        current_filter=status,
        current_page=page,
        total_pages=total_pages,
        total_orders=total_orders
    )


@routes.route('/')
def dashboard():
    page = int(request.args.get('page', 1))
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_connection()
    with conn.cursor() as cursor:
        # recent orders (paginated)
        cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT %s OFFSET %s", (per_page, offset))
        orders = cursor.fetchall()

        # counts
        cursor.execute("SELECT COUNT(*) AS total FROM orders")
        total_orders = cursor.fetchone()['total']
        cursor.execute("SELECT COUNT(*) AS confirmed FROM orders WHERE status = 'Confirmed'")
        confirmed_orders = cursor.fetchone()['confirmed']
        cursor.execute("SELECT COUNT(*) AS cancelled FROM orders WHERE status = 'Cancelled'")
        cancelled_orders = cursor.fetchone()['cancelled']
        cursor.execute("SELECT COUNT(*) AS pending FROM orders WHERE status = 'Pending'")
        pending_orders = cursor.fetchone()['pending']
        cursor.execute("SELECT COUNT(*) AS not_responding FROM orders WHERE status = 'Not Responding'")
        not_responding_orders = cursor.fetchone()['not_responding']
        cursor.execute("SELECT COUNT(*) AS to_process FROM orders WHERE status = 'To Process'")
        to_process_orders = cursor.fetchone()['to_process']
        cursor.execute("SELECT COUNT(*) AS failed_delivery FROM orders WHERE shipping_status = 'Failed Delivery'")
        failed_delivery_orders = cursor.fetchone()['failed_delivery']
        cursor.execute("SELECT COUNT(*) AS valued FROM orders WHERE customer_type = 'Valued'")
        valued_orders = cursor.fetchone()['valued']

        # Top products (by count, top 5)
        cursor.execute("""
            SELECT item_name, COUNT(*) AS cnt
            FROM orders
            WHERE item_name <> '' AND item_name IS NOT NULL
            GROUP BY item_name
            ORDER BY cnt DESC
            LIMIT 5
        """)
        tp = cursor.fetchall()
        top_products_labels = [r['item_name'] for r in tp]
        top_products_counts = [r['cnt'] for r in tp]

        # Orders over time (group by month YYYY-MM). Works for DATETIME column.
        cursor.execute("""
            SELECT DATE_FORMAT(created_at, '%Y-%m') AS ym, COUNT(*) AS cnt
            FROM orders
            WHERE created_at IS NOT NULL
            GROUP BY ym
            ORDER BY ym ASC
        """)
        oot = cursor.fetchall()
        orders_over_time_labels = [r['ym'] for r in oot if r['ym']]
        orders_over_time_counts = [r['cnt'] for r in oot if r['ym']]

        total_pages = (total_orders + per_page - 1) // per_page

    return render_template(
        "dashboard.html",
        total_orders=total_orders,
        confirmed_orders=confirmed_orders,
        cancelled_orders=cancelled_orders,
        pending_orders=pending_orders,
        not_responding_orders=not_responding_orders,
        to_process_orders=to_process_orders,
        failed_delivery_orders=failed_delivery_orders,
        valued_orders=valued_orders,
        top_products_labels=top_products_labels,
        top_products_counts=top_products_counts,
        orders_over_time_labels=orders_over_time_labels,
        orders_over_time_counts=orders_over_time_counts,
        orders=orders,
        current_page=page,
        total_pages=total_pages
    )


@routes.route('/orders')
def orders():
    page = max(int(request.args.get('page', 1)), 1)
    per_page = 10
    offset = (page - 1) * per_page

    q = (request.args.get('q') or '').strip()
    status = (request.args.get('status') or 'All').strip()

    where = []
    params = []

    if q:
        where.append("(order_number LIKE %s OR billing_name LIKE %s OR item_name LIKE %s OR billing_city LIKE %s OR billing_phone LIKE %s)")
        like = f"%{q}%"
        params.extend([like, like, like, like, like])

    if status and status != 'All':
        if status == 'Valued':
            where.append("customer_type = %s")
            params.append('Valued')
        else:
            # match either order status or shipping status
            where.append("(status = %s OR shipping_status = %s)")
            params.extend([status, status])

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) AS total FROM orders{where_sql}", params)
        total_orders = cursor.fetchone()['total']

        cursor.execute(
            f"SELECT * FROM orders{where_sql} ORDER BY id DESC LIMIT %s OFFSET %s",
            params + [per_page, offset]
        )
        orders = cursor.fetchall()

    total_pages = (total_orders + per_page - 1) // per_page

    return render_template(
        "orders.html",
        orders=orders,
        total_orders=total_orders,
        current_page=page,
        total_pages=total_pages
    )


@routes.route('/orders/bulk_update_status', methods=['POST'])
def bulk_update_status():
    data = request.get_json(force=True, silent=True) or {}
    ids = data.get('ids') or []
    status = data.get('status')
    if not ids or not status:
        return jsonify({"error": "ids and status are required"}), 400

    # Build placeholders safely for MySQL
    placeholders = ",".join(["%s"] * len(ids))
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute(f"UPDATE orders SET status = %s WHERE id IN ({placeholders})", [status] + ids)
        conn.commit()
    return jsonify({"updated": len(ids), "status": status})


@routes.route('/orders/bulk_delete', methods=['POST'])
def bulk_delete():
    data = request.get_json(force=True, silent=True) or {}
    ids = data.get('ids') or []
    if not ids:
        return jsonify({"error": "ids are required"}), 400

    placeholders = ",".join(["%s"] * len(ids))
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute(f"DELETE FROM orders WHERE id IN ({placeholders})", ids)
        conn.commit()
    return jsonify({"deleted": len(ids)})


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
                advance_delivery_charges=%s, cod_amount=%s, courier=%s, shipping_status=%s,
                notes=%s, preferred_courier=%s, tracking_number=%s, customer_type=%s
            WHERE id = %s
        """, (
            data.get("order_source", ''), data.get("order_number", ''), data.get("subtotal", 0), data.get("shipping", 0),
            float(data.get("subtotal", 0)) + float(data.get("shipping", 0)),
            data.get("discount_code", ''), data.get("discount_amount", 0),
            data.get("created_at", ''), data.get("quantity", 0), data.get("item_name", ''),
            data.get("billing_name", ''), data.get("billing_phone", ''),
            data.get("billing_street", ''), data.get("billing_city", ''), data.get("status", ''),
            data.get("advance_delivery_charges", ''), data.get("cod_amount", 0), data.get("courier", ''), data.get("shipping_status", ''),
            data.get("notes", ''), data.get("preferred_courier", ''), data.get("tracking_number", ''), data.get("customer_type", ''),
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
            billing_street, billing_city, status, advance_delivery_charges, cod_amount, courier, shipping_status,
            notes, preferred_courier, tracking_number, customer_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            data.get("order_source", ''), data.get("order_number", ''), data.get("subtotal", 0), data.get("shipping", 0),
            float(data.get("subtotal", 0)) + float(data.get("shipping", 0)),
            data.get("discount_code", ''), data.get("discount_amount", 0),
            data.get("created_at", ''), data.get("quantity", 0), data.get("item_name", ''),
            data.get("billing_name", ''), data.get("billing_phone", ''),
            data.get("billing_street", ''), data.get("billing_city", ''), data.get("status", ''),
            data.get("advance_delivery_charges", ''), data.get("cod_amount", 0), data.get("courier", ''), data.get("shipping_status", ''),
            data.get("notes", ''), data.get("preferred_courier", ''), data.get("tracking_number", ''), data.get("customer_type", '')
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
                    created_at = datetime.now()
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
                    row.get('Shipping Status', '').strip(),
                    row.get('Notes from customer', '').strip(),
                    row.get('Preferred Courier company', '').strip(),
                    row.get('Tracking number', '').strip(),
                    ''
                )
                if len(record) != 23:
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
                        advance_delivery_charges, cod_amount, courier, shipping_status,
                        notes, preferred_courier, tracking_number, customer_type
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        cursor.execute("UPDATE orders SET shipping_status = %s WHERE id = %s", (new_status, order_id))
        conn.commit()
    return jsonify({"status": "updated"})

@routes.route('/order/<int:order_id>/courier', methods=['PATCH'])
def update_courier(order_id):
    data = request.get_json()
    new_status = data.get('courier')
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE orders SET courier = %s WHERE id = %s", (new_status, order_id))
        conn.commit()
    return jsonify({"status": "updated"})

@routes.route('/order/<int:order_id>/preferred_courier', methods=['PATCH'])
def update_preferred_courier(order_id):
    data = request.get_json()
    new_preferred = data.get('preferred_courier')
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE orders SET preferred_courier = %s WHERE id = %s", (new_preferred, order_id))
        conn.commit()
    return jsonify({"status": "updated"})

@routes.route('/order/<int:order_id>/tracking_number', methods=['PATCH'])
def update_tracking_number(order_id):
    data = request.get_json()
    new_tracking = data.get('tracking_number')
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE orders SET tracking_number = %s WHERE id = %s", (new_tracking, order_id))
        conn.commit()
    return jsonify({"status": "updated"})

@routes.route('/order/<int:order_id>/customer_type', methods=['PATCH'])
def update_customer_type(order_id):
    data = request.get_json()
    new_type = data.get('customer_type')
    conn = get_connection()
    with conn.cursor() as cursor:
        cursor.execute("UPDATE orders SET customer_type = %s WHERE id = %s", (new_type, order_id))
        conn.commit()
    return jsonify({"status": "updated"})

def send_whatsapp_generic(message_type, where_clause, update_after_send=None):
    failed_numbers = []
    conn = get_connection()
    headless_mode = request.form.get("headless") is not None
    with conn.cursor() as cursor:
        cursor.execute(
            f"SELECT order_number, billing_name, item_name, billing_phone, total, tracking_number "
            f"FROM orders {where_clause}"
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
            name = user['billing_name'] or 'Customer'
            product = user['item_name'] or 'your product'
            phone = user['billing_phone']
            o_num = user['order_number']
            price = user['total']
            tracking = user.get('tracking_number', '')
            message = build_message(name, product, o_num, price, tracking, templates, message_type)
            link = f"https://web.whatsapp.com/send?phone={phone}"
            driver.execute_script(f"window.open('{link}','_blank');")
            human_delay(2,1)
            driver.switch_to.window(driver.window_handles[-1])
            human_delay(10,5)
            try:
                xpath = '//div[@contenteditable="true" and @data-tab="10"]'
                box = WebDriverWait(driver,15).until(EC.presence_of_element_located((By.XPATH, xpath)))
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
                if update_after_send:
                    with get_connection().cursor() as c2:
                        c2.execute(update_after_send, (o_num,))
                        c2.connection.commit()
                logger.info(f"Sent {message_type} message to {phone}")
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
        return jsonify({'message': f'{len(users)} {message_type} messages processed', 'failed_numbers': failed_numbers})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@routes.route('/send_whatsapp_messages', methods=['POST'])
def send_whatsapp_messages():
    msg_type = request.form.get('msgType')
    if msg_type == 'confirmation':
        return send_whatsapp_generic('confirmation', "WHERE status IN ('To Process', 'Not Responding')", "UPDATE orders SET status='Confirmed' WHERE order_number=%s")
    elif msg_type == 'return':
        return send_whatsapp_generic('return', "WHERE shipping_status = 'Failed Delivery'")
    elif msg_type == 'cancelled':
        return send_whatsapp_generic('cancelled', "WHERE status = 'Cancelled'")
    elif msg_type == 'valued':
        return send_whatsapp_generic('valued', "WHERE customer_type = 'Valued'")
    elif msg_type == 'tracking':
        return send_whatsapp_generic('tracking', "WHERE tracking_number != '' AND shipping_status = 'Shipped'")
    return jsonify({'error': 'Invalid message type'}), 400


@routes.route('/send_messages', methods=['POST'])
def send_messages():
    selected_types = request.form.getlist('message_types')
    headless_flag = request.form.get('headless')
    results = []
    mapping = {
        'confirmation': ("WHERE status IN ('To Process','Not Responding')", "UPDATE orders SET status='Confirmed' WHERE order_number=%s"),
        'return': ("WHERE shipping_status = 'Failed Delivery'", None),
        'cancelled': ("WHERE status = 'Cancelled'", None),
        'valued': ("WHERE customer_type = 'Valued'", None),
        'tracking': ("WHERE tracking_number != '' AND shipping_status = 'Shipped'", None)
    }
    if not selected_types:
        return jsonify({'error': 'No message types selected'}), 400

    for mt in selected_types:
        if mt in mapping:
            where_clause, update_after_send = mapping[mt]
            res = send_whatsapp_generic(mt, where_clause, update_after_send)
            try:
                data = res.get_json()
            except:
                data = {}
            results.append({mt: data})

    return jsonify({'message': 'Messages processed', 'details': results})



@routes.route('/orders/confirm_all', methods=['POST'])
def confirm_all_orders():
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute("UPDATE orders SET status = 'Confirmed' WHERE status IN ('To Process', 'Not Responding')")
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
    page = max(int(request.args.get('page', 1)), 1)
    per_page = 9
    offset = (page - 1) * per_page

    q = (request.args.get('q') or '').strip()
    category = (request.args.get('category') or 'All').strip()
    status = (request.args.get('status') or 'All').strip()

    where = []
    params = []

    if q:
        where.append("(template_name LIKE %s OR IFNULL(description,'') LIKE %s OR content LIKE %s)")
        like = f"%{q}%"
        params += [like, like, like]

    if category and category != 'All':
        where.append("COALESCE(category,'') = %s")
        params.append(category)

    if status and status != 'All':
        where.append("COALESCE(status,'Active') = %s")
        params.append(status)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    conn = get_connection()
    with conn.cursor() as c:
        c.execute(f"SELECT COUNT(*) AS total FROM message_templates{where_sql}", params)
        total = c.fetchone()['total']

        c.execute(
            f"""SELECT id, template_name, description, category, status, content,
                        created_at, updated_at
                 FROM message_templates
                 {where_sql}
                 ORDER BY updated_at DESC, id DESC
                 LIMIT %s OFFSET %s""",
            params + [per_page, offset]
        )
        rows = c.fetchall()

        c.execute("SELECT COUNT(*) AS total FROM message_templates")
        total_templates = c.fetchone()['total']
        c.execute("SELECT COUNT(*) AS active FROM message_templates WHERE status='Active'")
        active_templates = c.fetchone()['active']
        c.execute("SELECT COUNT(*) AS drafts FROM message_templates WHERE status='Draft'")
        draft_templates = c.fetchone()['drafts']
        c.execute("SELECT COUNT(DISTINCT COALESCE(category,'Orders')) AS cats FROM message_templates")
        categories_count = c.fetchone()['cats']

    def _display_title(name: str, cat: str | None) -> str:
        n = (name or '').lower()
        if n.startswith('return_'):      return 'Failed\nDelivery\nFollow-up'
        if n.startswith('tracking_'):    return 'Courier\nTracking Info'
        if n.startswith('cancelled_'):   return 'Cancelled\nOrder\nFollow-up'
        if n.startswith('valued_'):      return 'Valued\nCustomer\nPromotion'
        return 'Order\nConfirmation'

    enriched = []
    for r in rows:
        raw = r.get('content') or ''
        preview_text, lines_count, chars_count = '', 0, 0
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                lines_count = len(parsed)
                preview_text = (parsed[0] if parsed else '')[:120]
                chars_count = sum(len(x) for x in parsed if isinstance(x, str))
            else:
                s = str(parsed)
                lines_count = max(1, s.count('\n') + 1)
                preview_text = s[:120]
                chars_count = len(s)
        except Exception:
            s = str(raw)
            lines_count = max(1, s.count('\n') + 1)
            preview_text = s[:120]
            chars_count = len(s)

        r['display_title'] = _display_title(r.get('template_name'), r.get('category'))
        r['preview_text']  = preview_text
        r['lines_count']   = lines_count
        r['chars_count']   = chars_count
        enriched.append(r)

    total_pages = (total + per_page - 1) // per_page

    return render_template(
        "templates.html",
        templates=enriched,
        q=q, category=category, status=status,
        current_page=page, total_pages=total_pages, total=total,
        total_templates=total_templates, active_templates=active_templates,
        draft_templates=draft_templates, categories_count=categories_count
    )


def _preview_from_lines(lines: list[str]) -> str:
    # Join lines and substitute common placeholders with sample values
    sample = {
        'name': 'Ahmed',
        'order_id': 'ORD-1023',
        'order_num': 'ORD-1023',
        'product': 'Wireless Headphones',
        'price': 'Rs. 2,950',
        'tracking_link': 'https://track.example/XYZ',
        'tracking': 'TRK123456',
    }
    text = "\n".join(lines)
    for k, v in sample.items():
        text = text.replace('{'+k+'}', v)
    return text.strip()


@routes.route('/templates/<int:tpl_id>/preview', methods=['POST'])
def preview_template(tpl_id):
    data = request.get_json(force=True, silent=True) or {}
    lines = [s.strip() for s in (data.get('items') or []) if s and s.strip()]
    if not lines:
        # fallback: use DB content if form didn’t send anything
        conn = get_connection()
        with conn.cursor() as c:
            c.execute("SELECT content FROM message_templates WHERE id=%s", (tpl_id,))
            row = c.fetchone()
        try:
            lines = json.loads(row['content'] or '[]')
            if not isinstance(lines, list):
                lines = [str(lines)]
        except Exception:
            lines = [str(row['content'] or '')]

    return jsonify({'preview': _preview_from_lines(lines)})


@routes.route('/templates/preview', methods=['POST'])
def preview_template_ephemeral():
    data = request.get_json(silent=True) or {}
    items = data.get('items') or []
    return jsonify({"preview": _join_preview(items)})


@routes.route('/templates/<int:tpl_id>/json')
def template_json(tpl_id):
    conn = get_connection()
    with conn.cursor() as c:
        c.execute("""SELECT id, template_name, description, category, status, content,
                            created_at, updated_at
                     FROM message_templates WHERE id=%s""", (tpl_id,))
        row = c.fetchone()
    if not row:
        return jsonify({"error":"Not found"}), 404
    return jsonify(row)


def _next_copy_name(conn, base_name, max_len=50):
    """
    Generate a unique, length-safe copy name:
    <trimmed base> (Copy) / (Copy 2) / (Copy 3) ... within max_len chars.
    """
    base_name = (base_name or 'Untitled Template').strip()
    n = 1
    while True:
        suffix = " (Copy)" if n == 1 else f" (Copy {n})"
        limit = max_len - len(suffix)
        if limit < 1:
            candidate = suffix.strip()[:max_len]
        else:
            candidate = (base_name[:limit]).rstrip() + suffix
        with conn.cursor() as c:
            c.execute("SELECT 1 FROM message_templates WHERE template_name=%s LIMIT 1", (candidate,))
            exists = c.fetchone()
        if not exists:
            return candidate
        n += 1


@routes.route('/templates/<int:tpl_id>/duplicate', methods=['POST'])
def duplicate_template(tpl_id):
    conn = get_connection()
    with conn.cursor() as c:
        c.execute("SELECT * FROM message_templates WHERE id=%s", (tpl_id,))
        t = c.fetchone()
        if not t:
            return jsonify({"error": "Not found"}), 404

        new_name = _next_copy_name(conn, t['template_name'], max_len=50)

        c.execute("""
          INSERT INTO message_templates
            (template_name, description, category, status, content)
          VALUES (%s, %s, %s, %s, %s)
        """, (new_name, t.get('description'), t.get('category'), t.get('status'), t.get('content')))
        conn.commit()

    flash("Template duplicated", "success")
    return redirect(url_for('routes.list_templates'))



@routes.route('/templates/<int:tpl_id>/delete', methods=['POST'])
def delete_template(tpl_id):
    conn = get_connection()
    with conn.cursor() as c:
        c.execute("DELETE FROM message_templates WHERE id=%s", (tpl_id,))
        conn.commit()
    return jsonify({"ok": True})


@routes.route('/templates/<int:tpl_id>', methods=['GET', 'POST'])
def edit_template(tpl_id):
    conn = get_connection()
    if request.method == 'POST':
        # fields from form
        title = (request.form.get('template_name') or '').strip()
        category = (request.form.get('category') or 'Orders').strip()
        description = (request.form.get('description') or '').strip()
        status = (request.form.get('status') or 'Active').strip()

        # collect lines (ignore empty)
        items = [s.strip() for s in request.form.getlist('items') if s.strip()]
        content = json.dumps(items, ensure_ascii=False)

        with conn.cursor() as c:
            c.execute("""
                UPDATE message_templates
                   SET template_name=%s,
                       description=%s,
                       category=%s,
                       status=%s,
                       content=%s
                 WHERE id=%s
            """, (title, description, category, status, content, tpl_id))
            conn.commit()

        flash("Template updated", "success")
        return redirect(url_for('routes.list_templates'))

    # GET
    with conn.cursor() as c:
        c.execute("SELECT * FROM message_templates WHERE id=%s", (tpl_id,))
        tpl = c.fetchone()
    items = []
    try:
        items = json.loads(tpl.get('content') or '[]')
        if not isinstance(items, list):
            items = [str(items)]
    except Exception:
        items = [str(tpl.get('content') or '')]

    # sensible defaults if columns are missing
    tpl.setdefault('category', 'Orders')
    tpl.setdefault('status', 'Active')
    tpl.setdefault('description', '')

    return render_template('edit_template.html', template=tpl, items=items)


@routes.route('/templates/new', methods=['GET', 'POST'], endpoint='create_template')
def create_template():
    if request.method == 'POST':
        name = (request.form.get('template_name') or '').strip() or 'Untitled Template'
        name = name[:50]  # DB limit safeguard
        desc = (request.form.get('description') or '').strip()
        cat = (request.form.get('category') or 'Orders').strip()
        stat = (request.form.get('status') or 'Active').strip()
        items = request.form.getlist('items') or []
        content = json.dumps([s for s in items if str(s).strip()])

        conn = get_connection()
        with conn.cursor() as c:
            c.execute("""
                INSERT INTO message_templates (template_name, description, category, status, content, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (name, desc, cat, stat, content))
            conn.commit()
            c.execute("SELECT LAST_INSERT_ID() AS id")
            new_id = c.fetchone()['id']

        if 'application/json' in (request.headers.get('Accept') or '') or \
           request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({"id": new_id, "edit_url": url_for('routes.edit_template', tpl_id=new_id)})

        flash("Template created", "success")
        return redirect(url_for('routes.edit_template', tpl_id=new_id))

    # GET: Render edit_template.html with defaults
    template = {
        'id': None,
        'template_name': '',
        'description': '',
        'category': 'Orders',
        'status': 'Active',
        'updated_at': None,
        'created_at': None,
    }
    items = []
    return render_template('edit_template.html', template=template, items=items)


def _parse_lines(content):
    try:
        arr = json.loads(content or "[]")
        if isinstance(arr, list):
            return [str(x) for x in arr]
    except Exception:
        pass
    return []

def _join_preview(lines):
    return "\n".join([s for s in (lines or []) if str(s).strip()])


# ========= Customers (derived from orders) =========

from datetime import datetime, timedelta
from flask import send_file
import io
import csv

def _customers_base_sql():
    # Aggregates by a "customer key" (phone if present, otherwise NAME:<name>)
    # Pulls latest city/customer_type/preferred_courier via correlated subqueries.
    return """
      SELECT
        cust_key,
        MAX(billing_name)                        AS billing_name,
        MAX(NULLIF(billing_phone,''))            AS billing_phone,
        COUNT(*)                                 AS total_orders,
        COALESCE(SUM(total),0)                   AS total_spent,
        MIN(COALESCE(created_at, NOW()))         AS first_order,
        MAX(COALESCE(created_at, NOW()))         AS last_order,
        (
          SELECT o2.billing_city FROM orders o2
          WHERE (CASE WHEN o2.billing_phone IS NOT NULL AND o2.billing_phone<>'' 
                      THEN o2.billing_phone ELSE CONCAT('NAME:', o2.billing_name) END) = cust_key
          ORDER BY COALESCE(o2.created_at, NOW()) DESC, o2.id DESC
          LIMIT 1
        ) AS billing_city,
        (
          SELECT o2.customer_type FROM orders o2
          WHERE (CASE WHEN o2.billing_phone IS NOT NULL AND o2.billing_phone<>'' 
                      THEN o2.billing_phone ELSE CONCAT('NAME:', o2.billing_name) END) = cust_key
          ORDER BY COALESCE(o2.created_at, NOW()) DESC, o2.id DESC
          LIMIT 1
        ) AS customer_type,
        (
          SELECT o2.preferred_courier FROM orders o2
          WHERE (CASE WHEN o2.billing_phone IS NOT NULL AND o2.billing_phone<>'' 
                      THEN o2.billing_phone ELSE CONCAT('NAME:', o2.billing_name) END) = cust_key
          ORDER BY COALESCE(o2.created_at, NOW()) DESC, o2.id DESC
          LIMIT 1
        ) AS preferred_courier
      FROM (
        SELECT
          CASE WHEN billing_phone IS NOT NULL AND billing_phone<>'' 
               THEN billing_phone ELSE CONCAT('NAME:', billing_name) END AS cust_key,
          billing_name, billing_phone, total, created_at
        FROM orders
      ) t
      GROUP BY cust_key
    """

def _customers_counts(conn):
    base_sql = _customers_base_sql()
    with conn.cursor() as c:
        # total customers
        c.execute(f"SELECT COUNT(*) AS c FROM ({base_sql}) AS custs")
        total = c.fetchone()['c']

        # valued
        c.execute(f"SELECT COUNT(*) AS c FROM ({base_sql}) AS custs WHERE customer_type='Valued'")
        valued = c.fetchone()['c']

        # new (first order within last 30 days)
        c.execute(f"SELECT COUNT(*) AS c FROM ({base_sql}) AS custs WHERE first_order >= (NOW() - INTERVAL 30 DAY)")
        new30 = c.fetchone()['c']

        # inactive (last order older than 30 days)
        c.execute(f"SELECT COUNT(*) AS c FROM ({base_sql}) AS custs WHERE last_order < (NOW() - INTERVAL 30 DAY)")
        inactive = c.fetchone()['c']

    return total, valued, new30, inactive

def _fetch_customers(conn, q, segment, page, per_page):
    base_sql = _customers_base_sql()
    outer = f"SELECT * FROM ({base_sql}) AS custs"
    where = []
    params = []

    if q:
        like = f"%{q}%"
        where.append("(billing_name LIKE %s OR billing_phone LIKE %s OR billing_city LIKE %s)")
        params += [like, like, like]

    if segment == 'Valued':
        where.append("customer_type='Valued'")
    elif segment == 'New':
        where.append("first_order >= (NOW() - INTERVAL 30 DAY)")
    elif segment == 'Inactive':
        where.append("last_order < (NOW() - INTERVAL 30 DAY)")
    # 'All' => no extra clause

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    order_sql = " ORDER BY last_order DESC"

    # count for pagination
    with conn.cursor() as c:
        c.execute(f"SELECT COUNT(*) AS c FROM ({base_sql}) AS custs{where_sql}", params)
        total_filtered = c.fetchone()['c']

    offset = (page - 1) * per_page
    with conn.cursor() as c:
        c.execute(f"{outer}{where_sql}{order_sql} LIMIT %s OFFSET %s", params + [per_page, offset])
        rows = c.fetchall()

    # enhance rows for UI
    now = datetime.now()
    enhanced = []
    for r in rows:
        name = (r.get('billing_name') or '').strip() or '—'
        # initials
        initials = ''.join([p[0] for p in name.split()[:2] if p])[:2].upper() or 'CU'
        # badge
        last_order = r.get('last_order')
        first_order = r.get('first_order')
        total_orders = int(r.get('total_orders') or 0)

        # compute ages safely
        def _days(dt):
            try:
                return (now - dt).days
            except Exception:
                return 0

        days_since_last = _days(last_order) if last_order else 0
        days_since_first = _days(first_order) if first_order else 0

        if (r.get('customer_type') or '') == 'Valued':
            badge = ('Valued', 'bg-orange-100 text-orange-500')
        elif days_since_last > 30:
            badge = ('Inactive', 'bg-gray-200 text-gray-500')
        elif days_since_first <= 30:
            badge = ('New', 'bg-green-100 text-green-600')
        else:
            badge = ('Regular', 'bg-green-100 text-green-600')

        # human "ago"
        def human_ago(d):
            if d <= 1: return "1 day ago"
            if d < 7:  return f"{d} days ago"
            w = d // 7
            if w == 1: return "1 week ago"
            if w < 5:  return f"{w} weeks ago"
            m = d // 30
            if m <= 1: return "1 month ago"
            return f"{m} months ago"

        enhanced.append({
            **r,
            'initials': initials,
            'badge_label': badge[0],
            'badge_class': badge[1],
            'joined_date': (first_order.strftime('%Y-%m-%d') if first_order else '—'),
            'last_order_ago': human_ago(days_since_last) if last_order else '—',
            'total_spent_fmt': f"PKR {float(r.get('total_spent') or 0):,.2f}",
        })

    return enhanced, total_filtered
# routes/routes.py  (drop-in replacement for your /customers)
from flask import Blueprint, render_template, request, jsonify
from models.db import get_connection
from datetime import datetime, date

# ... existing imports & blueprint setup ...

@routes.route('/customers')
def customers():
    # -------- params ----------
    page      = max(int(request.args.get('page', 1) or 1), 1)
    per_page  = max(int(request.args.get('per_page', 18) or 18), 1)   # 6 x 3 cards by default
    q         = (request.args.get('q') or '').strip()
    segment   = (request.args.get('segment') or 'All').strip()  # All | Valued | Inactive30 | New | Regular

    offset = (page - 1) * per_page

    # -------- WHERE pieces (applied to the "latest snapshot" l and aggregates a) ----------
    where_sql = []
    params = []

    # text search on latest name/phone/city (keeps it snappy and intuitive)
    if q:
        like = f"%{q}%"
        where_sql.append("(l.billing_name LIKE %s OR l.billing_phone LIKE %s OR l.billing_city LIKE %s)")
        params.extend([like, like, like])

    # segment filter
    if segment == 'Valued':
        where_sql.append("l.customer_type = 'Valued'")
    elif segment == 'Inactive30':
        where_sql.append("a.last_order_at < (NOW() - INTERVAL 30 DAY)")
    elif segment == 'New':
        # Joined this month (first order)
        where_sql.append("a.joined_at >= DATE_FORMAT(CURDATE(), '%Y-%m-01')")
    elif segment == 'Regular':
        where_sql.append("""
            ( (l.customer_type IS NULL OR l.customer_type <> 'Valued')
              AND a.last_order_at >= (NOW() - INTERVAL 30 DAY)
              AND a.joined_at < DATE_FORMAT(CURDATE(), '%Y-%m-01') )
        """)
    # else: All (no extra condition)

    where_clause = ("WHERE " + " AND ".join(where_sql)) if where_sql else ""

    # -------- main page query (one row per customer for current page) ----------
    # Uses CTEs and window function to grab latest row per customer_key.
    main_sql = f"""
    WITH base AS (
        SELECT
            id, customer_key, billing_name, billing_phone, billing_city, billing_street,
            preferred_courier, customer_type, created_at, total,
            ROW_NUMBER() OVER (PARTITION BY customer_key ORDER BY created_at DESC, id DESC) AS rn
        FROM orders
    ),
    latest AS (
        SELECT *
        FROM base
        WHERE rn = 1
    ),
    agg AS (
        SELECT
            customer_key,
            COUNT(*)               AS orders_count,
            SUM(total)             AS total_spent,
            MIN(created_at)        AS joined_at,
            MAX(created_at)        AS last_order_at
        FROM orders
        GROUP BY customer_key
    )
    SELECT
        l.customer_key,
        l.billing_name,
        l.billing_phone,
        l.billing_city,
        l.billing_street,
        l.preferred_courier,
        l.customer_type,
        a.orders_count,
        a.total_spent,
        a.joined_at,
        a.last_order_at
    FROM latest l
    JOIN agg a USING (customer_key)
    {where_clause}
    ORDER BY a.last_order_at DESC
    LIMIT %s OFFSET %s
    """

    # -------- count query (total customers after filters) ----------
    count_sql = f"""
    WITH base AS (
        SELECT
            id, customer_key, billing_name, billing_phone, billing_city, customer_type, created_at,
            ROW_NUMBER() OVER (PARTITION BY customer_key ORDER BY created_at DESC, id DESC) AS rn
        FROM orders
    ),
    latest AS (
        SELECT * FROM base WHERE rn = 1
    ),
    agg AS (
        SELECT
            customer_key,
            MIN(created_at) AS joined_at,
            MAX(created_at) AS last_order_at
        FROM orders
        GROUP BY customer_key
    )
    SELECT COUNT(*) AS cnt
    FROM latest l
    JOIN agg a USING (customer_key)
    {where_clause}
    """

    # -------- summary cards (computed with indexed fields) ----------
    summary_sql = {
        "total": """
            SELECT COUNT(*) AS c FROM (
              SELECT customer_key FROM orders GROUP BY customer_key
            ) x
        """,
        "valued": """
            SELECT COUNT(*) AS c FROM (
              SELECT customer_key
              FROM orders
              GROUP BY customer_key
              HAVING MAX(customer_type = 'Valued') = 1
            ) x
        """,
        "new_month": """
            SELECT COUNT(*) AS c FROM (
              SELECT customer_key, MIN(created_at) AS joined_at
              FROM orders
              GROUP BY customer_key
              HAVING joined_at >= DATE_FORMAT(CURDATE(), '%Y-%m-01')
            ) x
        """,
        "inactive30": """
            SELECT COUNT(*) AS c FROM (
              SELECT customer_key, MAX(created_at) AS last_at
              FROM orders
              GROUP BY customer_key
              HAVING last_at < (NOW() - INTERVAL 30 DAY)
            ) x
        """
    }

    conn = get_connection()
    with conn.cursor() as c:
        # main page data
        c.execute(main_sql, params + [per_page, offset])
        rows = c.fetchall()

        # total count
        c.execute(count_sql, params)
        total_customers_filtered = c.fetchone()['cnt']

        # summary cards
        c.execute(summary_sql["total"]);     total_customers = c.fetchone()['c']
        c.execute(summary_sql["valued"]);    valued_customers = c.fetchone()['c']
        c.execute(summary_sql["new_month"]); new_this_month  = c.fetchone()['c']
        c.execute(summary_sql["inactive30"]);inactive_30     = c.fetchone()['c']

    total_pages = max((total_customers_filtered + per_page - 1) // per_page, 1)

    enriched = []
    now = datetime.utcnow()
    for r in rows:
        badge = 'Regular'
        if r['customer_type'] == 'Valued':
            badge = 'Valued'
        elif r['last_order_at'] and (now - r['last_order_at']).days > 30:
            badge = 'Inactive'
        elif r['joined_at'] and r['joined_at'].date() >= date.today().replace(day=1):
            badge = 'New'
        enriched.append({**r, 'badge': badge})

    return render_template(
        'customers.html',
        customers=enriched,
        q=q,
        segment=segment,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_filtered=total_customers_filtered,
        cards={
            "total": total_customers,
            "valued": valued_customers,
            "new_month": new_this_month,
            "inactive30": inactive_30
        }
    )


@routes.route('/customers/export')
def customers_export():
    # export with current filters
    q = (request.args.get('q') or '').strip()
    segment = (request.args.get('segment') or 'All').strip()

    conn = get_connection()
    # get all (no pagination) for export
    rows, _ = _fetch_customers(conn, q, segment, page=1, per_page=10_000_000)

    # CSV in-memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Name','Phone','City','Customer Type','Preferred Courier',
        'First Order','Last Order','Total Orders','Total Spent'
    ])
    for r in rows:
        writer.writerow([
            r.get('billing_name') or '',
            r.get('billing_phone') or '',
            r.get('billing_city') or '',
            r.get('customer_type') or '',
            r.get('preferred_courier') or '',
            r.get('first_order') or '',
            r.get('last_order') or '',
            r.get('total_orders') or 0,
            f"{float(r.get('total_spent') or 0):.2f}"
        ])
    mem = io.BytesIO(output.getvalue().encode('utf-8'))
    mem.seek(0)
    filename = 'customers_export.csv'
    return send_file(mem, mimetype='text/csv', as_attachment=True, download_name=filename)
