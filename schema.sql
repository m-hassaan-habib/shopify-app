CREATE DATABASE IF NOT EXISTS shopify_orders;
USE shopify_orders;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_source VARCHAR(255),
    order_number VARCHAR(255),
    subtotal FLOAT,
    shipping FLOAT,
    total FLOAT,
    discount_code VARCHAR(255),
    discount_amount FLOAT,
    created_at DATETIME,
    quantity INT,
    item_name VARCHAR(255),
    billing_name VARCHAR(255),
    billing_phone VARCHAR(255),
    billing_street TEXT,
    billing_city VARCHAR(255),
    status VARCHAR(255),
    advance_delivery_charges VARCHAR(50),
    cod_amount FLOAT,
    courier VARCHAR(255),
    shipping_status VARCHAR(255),
    notes TEXT,
    preferred_courier VARCHAR(255),
    tracking_number VARCHAR(255),
    customer_type VARCHAR(255) DEFAULT NULL
);


CREATE TABLE message_templates (
  id INT AUTO_INCREMENT PRIMARY KEY,
  template_name VARCHAR(50) NOT NULL UNIQUE,
  description VARCHAR(255) NULL,
  category VARCHAR(32) NOT NULL DEFAULT 'Orders',
  status VARCHAR(16)  NOT NULL DEFAULT 'Active',
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT IGNORE INTO message_templates (template_name, content) VALUES
('return_greetings', '["Hi", "Hello"]'),
('return_intros', '["Your order was returned due to delivery issues."]'),
('return_order_lines', '["Order details: {product}, #{order_num}, Rs. {price}"]'),
('return_requests', '["Do you still need it? We can resend via another courier."]'),
('return_closings', '["Please reply soon."]'),
('cancelled_greetings', '["Hi", "Hello"]'),
('cancelled_intros', '["We noticed your past order was cancelled."]'),
('cancelled_order_lines', '["We have a new range of products now."]'),
('cancelled_requests', '["Are you interested in checking them out?"]'),
('cancelled_closings', '["Best regards."]'),
('valued_greetings', '["Hi valued customer", "Hello"]'),
('valued_intros', '["Thank you for your past high-value orders."]'),
('valued_order_lines', '["Discover our latest products and exclusive bundles."]'),
('valued_requests', '["Special deals just for you."]'),
('valued_closings', '["Shop now!"]'),
('tracking_greetings', '["Hi", "Hello"]'),
('tracking_intros', '["Your order has been shipped."]'),
('tracking_order_lines', '["Track your parcel with this number."]'),
('tracking_closings', '["Happy shopping."]');

ALTER TABLE orders
  ADD COLUMN customer_key VARCHAR(512)
  GENERATED ALWAYS AS (
    COALESCE(
      NULLIF(TRIM(billing_phone), ''),
      CONCAT('N:', COALESCE(TRIM(billing_name),''), '|C:', COALESCE(TRIM(billing_city),''))
    )
  ) STORED;


CREATE INDEX idx_orders_customer_key           ON orders (customer_key);
CREATE INDEX idx_orders_created_at             ON orders (created_at);
CREATE INDEX idx_orders_customer_type          ON orders (customer_type);
CREATE INDEX idx_orders_key_created_id         ON orders (customer_key, created_at, id);

CREATE INDEX idx_orders_billing_city           ON orders (billing_city);
CREATE INDEX idx_orders_billing_phone          ON orders (billing_phone);

ALTER TABLE orders ADD FULLTEXT idx_orders_fulltext (billing_name, billing_city);
