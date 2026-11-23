-- Sunrise Bakery Management System (SBMS)
-- Database schema, MySQL 8+
-- Tables follow the suggested design in the case study, plus audit_log for auditability.

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS audit_log, sale_items, sales, order_items, customer_orders, customers,
    stock_movements, production_ingredient_usage, production_batches, recipe_ingredients,
    recipes, ingredient_batches, ingredient_deliveries, ingredients, suppliers, products,
    product_categories, users;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE users (
    user_id        INT AUTO_INCREMENT PRIMARY KEY,
    username       VARCHAR(40)  NOT NULL UNIQUE,
    password_hash  VARCHAR(100) NOT NULL,
    full_name      VARCHAR(100) NOT NULL,
    role           ENUM('Administrator','Manager','Production','Sales','Inventory') NOT NULL,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    failed_logins  INT NOT NULL DEFAULT 0,
    locked_until   DATETIME NULL,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE product_categories (
    category_id  INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE products (
    product_id      INT AUTO_INCREMENT PRIMARY KEY,
    product_code    VARCHAR(20)  NOT NULL UNIQUE,
    name            VARCHAR(100) NOT NULL,
    category_id     INT NOT NULL,
    description     VARCHAR(255),
    selling_price   DECIMAL(10,2) NOT NULL,
    stock_quantity  INT NOT NULL DEFAULT 0,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES product_categories(category_id),
    CONSTRAINT chk_products_price CHECK (selling_price >= 0),
    CONSTRAINT chk_products_stock CHECK (stock_quantity >= 0)
);

CREATE TABLE suppliers (
    supplier_id     INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    contact_person  VARCHAR(100),
    phone           VARCHAR(20),
    email           VARCHAR(100),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE ingredients (
    ingredient_id     INT AUTO_INCREMENT PRIMARY KEY,
    ingredient_code   VARCHAR(20)  NOT NULL UNIQUE,
    name              VARCHAR(100) NOT NULL,
    unit              ENUM('kg','g','L','ml','pcs') NOT NULL,
    current_quantity  DECIMAL(12,3) NOT NULL DEFAULT 0,
    reorder_level     DECIMAL(12,3) NOT NULL DEFAULT 0,
    supplier_id       INT NULL,
    CONSTRAINT fk_ingredients_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    CONSTRAINT chk_ingredients_qty CHECK (current_quantity >= 0),
    CONSTRAINT chk_ingredients_reorder CHECK (reorder_level >= 0)
);

CREATE TABLE ingredient_deliveries (
    delivery_id    INT AUTO_INCREMENT PRIMARY KEY,
    supplier_id    INT NOT NULL,
    delivery_date  DATE NOT NULL,
    reference      VARCHAR(50) NOT NULL,
    received_by    INT NOT NULL,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_deliveries_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
    CONSTRAINT fk_deliveries_user FOREIGN KEY (received_by) REFERENCES users(user_id),
    CONSTRAINT uq_delivery_ref UNIQUE (supplier_id, reference)
);

CREATE TABLE ingredient_batches (
    batch_id            INT AUTO_INCREMENT PRIMARY KEY,
    delivery_id         INT NOT NULL,
    ingredient_id       INT NOT NULL,
    batch_number        VARCHAR(40) NOT NULL,
    quantity_received   DECIMAL(12,3) NOT NULL,
    quantity_remaining  DECIMAL(12,3) NOT NULL,
    expiry_date         DATE NOT NULL,
    CONSTRAINT fk_batches_delivery FOREIGN KEY (delivery_id) REFERENCES ingredient_deliveries(delivery_id),
    CONSTRAINT fk_batches_ingredient FOREIGN KEY (ingredient_id) REFERENCES ingredients(ingredient_id),
    CONSTRAINT uq_batch UNIQUE (ingredient_id, batch_number),
    CONSTRAINT chk_batch_received CHECK (quantity_received > 0),
    CONSTRAINT chk_batch_remaining CHECK (quantity_remaining >= 0)
);

CREATE TABLE recipes (
    recipe_id       INT AUTO_INCREMENT PRIMARY KEY,
    product_id      INT NOT NULL,
    standard_yield  INT NOT NULL,
    is_current      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_recipes_product FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT chk_recipes_yield CHECK (standard_yield > 0)
);

CREATE TABLE recipe_ingredients (
    recipe_id      INT NOT NULL,
    ingredient_id  INT NOT NULL,
    quantity       DECIMAL(12,3) NOT NULL,
    PRIMARY KEY (recipe_id, ingredient_id),
    CONSTRAINT fk_ri_recipe FOREIGN KEY (recipe_id) REFERENCES recipes(recipe_id),
    CONSTRAINT fk_ri_ingredient FOREIGN KEY (ingredient_id) REFERENCES ingredients(ingredient_id),
    CONSTRAINT chk_ri_qty CHECK (quantity > 0)
);

CREATE TABLE production_batches (
    production_batch_id  INT AUTO_INCREMENT PRIMARY KEY,
    product_id           INT NOT NULL,
    recipe_id            INT NOT NULL,
    planned_quantity     INT NOT NULL,
    actual_quantity      INT NULL,
    wasted_quantity      INT NOT NULL DEFAULT 0,
    production_date      DATE NOT NULL,
    staff_id             INT NOT NULL,
    status               ENUM('Planned','Completed','Cancelled') NOT NULL DEFAULT 'Planned',
    completed_at         DATETIME NULL,
    CONSTRAINT fk_pb_product FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT fk_pb_recipe FOREIGN KEY (recipe_id) REFERENCES recipes(recipe_id),
    CONSTRAINT fk_pb_staff FOREIGN KEY (staff_id) REFERENCES users(user_id),
    CONSTRAINT chk_pb_planned CHECK (planned_quantity > 0),
    CONSTRAINT chk_pb_actual CHECK (actual_quantity IS NULL OR actual_quantity >= 0),
    CONSTRAINT chk_pb_waste CHECK (wasted_quantity >= 0)
);

CREATE TABLE production_ingredient_usage (
    usage_id             INT AUTO_INCREMENT PRIMARY KEY,
    production_batch_id  INT NOT NULL,
    ingredient_id        INT NOT NULL,
    quantity_used        DECIMAL(12,3) NOT NULL,
    CONSTRAINT fk_piu_batch FOREIGN KEY (production_batch_id) REFERENCES production_batches(production_batch_id),
    CONSTRAINT fk_piu_ingredient FOREIGN KEY (ingredient_id) REFERENCES ingredients(ingredient_id),
    CONSTRAINT chk_piu_qty CHECK (quantity_used > 0)
);

-- One row per change to ingredient or product stock. quantity is signed (+ in, - out).
CREATE TABLE stock_movements (
    movement_id    INT AUTO_INCREMENT PRIMARY KEY,
    ingredient_id  INT NULL,
    product_id     INT NULL,
    movement_type  ENUM('DELIVERY','PRODUCTION_USE','PRODUCTION_OUTPUT','SALE','ORDER',
                        'WASTE','ADJUSTMENT','ORDER_RETURN') NOT NULL,
    quantity       DECIMAL(12,3) NOT NULL,
    reference      VARCHAR(100),
    user_id        INT NOT NULL,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_sm_ingredient FOREIGN KEY (ingredient_id) REFERENCES ingredients(ingredient_id),
    CONSTRAINT fk_sm_product FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT fk_sm_user FOREIGN KEY (user_id) REFERENCES users(user_id),
    CONSTRAINT chk_sm_target CHECK ((ingredient_id IS NULL) <> (product_id IS NULL))
);

CREATE TABLE customers (
    customer_id  INT AUTO_INCREMENT PRIMARY KEY,
    full_name    VARCHAR(100) NOT NULL,
    phone        VARCHAR(20)  NOT NULL,
    email        VARCHAR(100),
    CONSTRAINT uq_customer_phone UNIQUE (phone)
);

CREATE TABLE customer_orders (
    order_id              INT AUTO_INCREMENT PRIMARY KEY,
    order_ref             VARCHAR(20) NOT NULL UNIQUE,
    customer_id           INT NOT NULL,
    order_date            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    collection_datetime   DATETIME NOT NULL,
    total_cost            DECIMAL(10,2) NOT NULL,
    status                ENUM('Received','Confirmed','In Preparation','Ready for Collection',
                               'Collected','Cancelled') NOT NULL DEFAULT 'Received',
    is_special            BOOLEAN NOT NULL DEFAULT FALSE,
    special_instructions  VARCHAR(500),
    cake_size             VARCHAR(30),
    flavour               VARCHAR(50),
    design_notes          VARCHAR(500),
    items_prepared        BOOLEAN NOT NULL DEFAULT FALSE,
    created_by            INT NOT NULL,
    CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    CONSTRAINT fk_orders_user FOREIGN KEY (created_by) REFERENCES users(user_id),
    CONSTRAINT chk_orders_total CHECK (total_cost >= 0)
);

CREATE TABLE order_items (
    order_item_id  INT AUTO_INCREMENT PRIMARY KEY,
    order_id       INT NOT NULL,
    product_id     INT NOT NULL,
    quantity       INT NOT NULL,
    unit_price     DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_oi_order FOREIGN KEY (order_id) REFERENCES customer_orders(order_id),
    CONSTRAINT fk_oi_product FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT chk_oi_qty CHECK (quantity > 0),
    CONSTRAINT chk_oi_price CHECK (unit_price >= 0)
);

CREATE TABLE sales (
    sale_id         INT AUTO_INCREMENT PRIMARY KEY,
    sale_datetime   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    staff_id        INT NOT NULL,
    total           DECIMAL(10,2) NOT NULL,
    payment_method  ENUM('Cash','Card','Bank Transfer') NOT NULL,
    CONSTRAINT fk_sales_staff FOREIGN KEY (staff_id) REFERENCES users(user_id),
    CONSTRAINT chk_sales_total CHECK (total >= 0)
);

CREATE TABLE sale_items (
    sale_item_id  INT AUTO_INCREMENT PRIMARY KEY,
    sale_id       INT NOT NULL,
    product_id    INT NOT NULL,
    quantity      INT NOT NULL,
    unit_price    DECIMAL(10,2) NOT NULL,
    CONSTRAINT fk_si_sale FOREIGN KEY (sale_id) REFERENCES sales(sale_id),
    CONSTRAINT fk_si_product FOREIGN KEY (product_id) REFERENCES products(product_id),
    CONSTRAINT chk_si_qty CHECK (quantity > 0),
    CONSTRAINT chk_si_price CHECK (unit_price >= 0)
);

-- Price changes, stock adjustments, order cancellations and account changes.
CREATE TABLE audit_log (
    audit_id    INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT NOT NULL,
    action      VARCHAR(40)  NOT NULL,
    entity      VARCHAR(40)  NOT NULL,
    entity_id   INT NOT NULL,
    details     VARCHAR(500),
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_products_name ON products(name);
CREATE INDEX idx_batches_expiry ON ingredient_batches(expiry_date);
CREATE INDEX idx_orders_status ON customer_orders(status, collection_datetime);
CREATE INDEX idx_sales_date ON sales(sale_datetime);
CREATE INDEX idx_movements_date ON stock_movements(created_at);
