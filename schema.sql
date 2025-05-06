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
    shipping_status VARCHAR(255)
);
