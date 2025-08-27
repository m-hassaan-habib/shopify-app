
# Order Management System

This is a Flask-based web application for managing e-commerce orders, importing orders via CSV, sending WhatsApp messages, and tracking order statuses. It includes a dashboard, order filtering, customer type management, and campaign messaging.

---

## Prerequisites

- Python 3.8+
- MySQL or MariaDB (preferred) or PostgreSQL 12+
- Chrome browser (for WhatsApp Web automation)
- Git

---

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <repository-url>
cd <repository-directory>
````

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt** should contain:

```
flask==2.0.1
pymysql==1.1.0
python-dotenv==1.0.1
selenium==4.10.0
webdriver-manager==3.8.3
```

### 4. Configure Environment

Copy the sample `.env`:

```bash
cp .env.sample .env
```

Edit `.env` with your database credentials:

```ini
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=yourpassword
DB_NAME=shopify_orders
SECRET_KEY=supersecret
```

### 5. Initialize Database

Ensure MySQL/MariaDB is running. Then:

```bash
mysql -u <user> -p -e "CREATE DATABASE shopify_orders;"
mysql -u <user> -p shopify_orders < schema.sql
```

### 6. Run the Application

```bash
python app.py
```

Access the app at:
[http://localhost:5003](http://localhost:5003)

---

## Features

* Dashboard

  * Order stats: Total, Confirmed, Cancelled, Pending, Not Responding, To Process, Failed Delivery, Valued Customers
  * Charts for top products and cities
  * Pagination for order list
* Order Management

  * Import orders via CSV
  * Confirm or delete all orders
  * Update order status, shipping status, courier, tracking number
  * Mark customers as valued
* WhatsApp Messaging

  * Automated messaging using WhatsApp Web (Selenium + Chrome)
  * Campaigns supported:

    * Confirmation (To Process / Not Responding)
    * Returns (Failed Delivery / Returned)
    * Cancelled Orders (product promotions)
    * Valued Customers (exclusive bundles)
    * Tracking (courier and tracking number)
* Templates

  * Manage message templates for each campaign
  * Templates stored in the database as JSON arrays

---

## CSV Import Format

The CSV must contain the following columns:

```
Order placed, Order #, Subtotal, Shipping, Discount Code, Discount Amount,
Created at, Lineitem quantity, Lineitem name, Billing Name, Billing Phone,
Billing Street, Billing City, Status, Advance Delivery Charges, COD Amount,
Courier, Shipping Status, Preferred Courier company, Tracking number,
Shipping charges, Confirmation via Call/whatsapp, Return Check, Valued Customer
```

### Example

```csv
Order placed,Order #,Subtotal,Shipping,Discount Code,Discount Amount,Created at,Lineitem quantity,Lineitem name,Billing Name,Billing Phone,Billing Street,Billing City,Status,Advance Delivery Charges,COD Amount,Courier,Shipping Status,Preferred Courier company,Tracking number
Shopify,ORD123,1000,200,CODE10,50,2025-08-27,2,Product A,John Doe,923001234567,123 Main St,Karachi,Pending,,1200,TCS,Shipped,TCS,TRACK123
```

---

## WhatsApp Automation

* Requires Chrome installed
* First run: scan QR code to log in to WhatsApp Web
* Session is stored locally in `whatsapp_session/`
* Headless mode can be enabled/disabled from the dashboard
* Messages are sent in small batches to prevent rate-limiting

---

## Database Schema

### orders

* Stores all order details
* Includes fields: order\_number, billing\_name, courier, tracking\_number, valued\_customer, and others

### message\_templates

* Stores WhatsApp message templates
* Content is a JSON array of messages that rotate randomly

---

## Routes

| Endpoint                      | Method         | Description                                      |
| ----------------------------- | -------------- | ------------------------------------------------ |
| `/`                           | GET            | Dashboard with stats and orders                  |
| `/orders/status/<status>`     | GET            | Filtered orders view                             |
| `/import`                     | POST           | Import orders from CSV                           |
| `/send_whatsapp`              | POST           | Send confirmation messages                       |
| `/send_returns`               | POST           | Send return messages                             |
| `/send_cancelled`             | POST           | Send cancelled order messages                    |
| `/send_valued`                | POST           | Send valued customer messages                    |
| `/send_tracking`              | POST           | Send tracking messages (optional courier filter) |
| `/order/<id>`                 | GET/PUT/DELETE | Get, update, delete order                        |
| `/order/<id>/status`          | PATCH          | Update order status                              |
| `/order/<id>/shipping_status` | PATCH          | Update shipping status                           |
| `/order/<id>/courier`         | PATCH          | Update courier                                   |
| `/order/<id>/valued`          | PATCH          | Toggle valued flag                               |
| `/templates`                  | GET            | List templates                                   |
| `/templates/<id>`             | GET/POST       | Edit a template                                  |

---

