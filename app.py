
import os
import sqlite3

from functools import wraps
from flask import Flask, render_template, request, redirect, session
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__)

# Secret key environment variable se lena
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-to-a-new-random-secret-key"
)

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False
)


# ================= DATABASE =================

os.makedirs("database", exist_ok=True)

DB_PATH = "database/shahnuvay.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():

    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            image TEXT,
            stock INTEGER DEFAULT 0
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            customer_name TEXT,
            phone TEXT,
            address TEXT,
            total REAL NOT NULL,
            status TEXT DEFAULT 'Pending'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id)
        )
    """)

    # Existing database mein missing columns add karna

    columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(orders)"
        ).fetchall()
    ]

    if "customer_id" not in columns:
        conn.execute(
            "ALTER TABLE orders ADD COLUMN customer_id INTEGER"
        )

    if "customer_name" not in columns:
        conn.execute(
            "ALTER TABLE orders ADD COLUMN customer_name TEXT"
        )

    if "phone" not in columns:
        conn.execute(
            "ALTER TABLE orders ADD COLUMN phone TEXT"
        )

    if "address" not in columns:
        conn.execute(
            "ALTER TABLE orders ADD COLUMN address TEXT"
        )

    if "total" not in columns:
        conn.execute(
            "ALTER TABLE orders ADD COLUMN total REAL"
        )

    if "status" not in columns:
        conn.execute(
            "ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'Pending'"
        )

    conn.commit()
    conn.close()


create_tables()


# ================= LOGIN REQUIRED =================

def login_required(route_function):

    @wraps(route_function)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect("/login")

        return route_function(*args, **kwargs)

    return wrapper


# ================= SIGNUP =================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    success_message = ""
    error_message = ""

    if request.method == "POST":

        name = request.form["name"].strip()
        email = request.form["email"].lower().strip()
        password = request.form["password"]

        if not name or not email:
            error_message = "Please fill all fields."

        elif len(password) < 8:
            error_message = "Password must be at least 8 characters."

        else:

            password_hash = generate_password_hash(password)

            conn = get_db()

            try:

                conn.execute(
                    """
                    INSERT INTO users (name, email, password)
                    VALUES (?, ?, ?)
                    """,
                    (name, email, password_hash)
                )

                conn.commit()

                success_message = (
                    "Account created successfully! Please log in."
                )

            except sqlite3.IntegrityError:

                error_message = "This email is already registered."

            finally:
                conn.close()

    return render_template(
        "signup.html",
        success_message=success_message,
        error_message=error_message
    )


# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].lower().strip()
        password = request.form["password"]

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):

            session.clear()
            session["user_id"] = user["id"]
            session["role"] = user["role"]

            return redirect("/")

        return "Invalid email or password."

    return render_template("login.html")


# ================= LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ================= HOME =================

@app.route("/")
def home():

    conn = get_db()

    products = conn.execute(
        "SELECT * FROM products ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return render_template(
        "index.html",
        products=products
    )


# ================= SHOP =================

@app.route("/shop")
def shop():

    search_query = request.args.get("q", "").strip()

    conn = get_db()

    if search_query:

        products = conn.execute(
            """
            SELECT * FROM products
            WHERE name LIKE ?
               OR description LIKE ?
            ORDER BY id DESC
            """,
            (f"%{search_query}%", f"%{search_query}%")
        ).fetchall()

    else:

        products = conn.execute(
            "SELECT * FROM products ORDER BY id DESC"
        ).fetchall()

    conn.close()

    return render_template(
        "shop.html",
        products=products,
        search_query=search_query
    )


# ================= PRODUCT DETAILS =================

@app.route("/product/<int:product_id>")
def product_details(product_id):

    conn = get_db()

    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    conn.close()

    if product is None:
        return "Product not found!", 404

    return render_template(
        "product_details.html",
        product=product
    )


# ================= ADD TO CART =================

@app.route("/add-to-cart/<int:product_id>", methods=["POST"])
def add_to_cart(product_id):

    conn = get_db()

    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    conn.close()

    if product is None:
        return "Product not found!", 404

    if product["stock"] <= 0:
        return "Product is out of stock!", 400

    cart = session.get("cart", {})

    product_key = str(product_id)
    current_quantity = cart.get(product_key, 0)

    if current_quantity >= product["stock"]:
        return "Not enough stock!", 400

    cart[product_key] = current_quantity + 1

    session["cart"] = cart

    return redirect("/cart")


# ================= CART =================

@app.route("/cart")
def cart():

    cart_items = session.get("cart", {})

    products = []
    total = 0

    conn = get_db()

    for product_id, quantity in cart_items.items():

        product = conn.execute(
            "SELECT * FROM products WHERE id = ?",
            (product_id,)
        ).fetchone()

        if product:

            item = dict(product)

            item["quantity"] = quantity
            item["subtotal"] = item["price"] * quantity

            total += item["subtotal"]

            products.append(item)

    conn.close()

    return render_template(
        "cart.html",
        products=products,
        total=total
    )


# ================= REMOVE FROM CART =================

@app.route("/remove-from-cart/<int:product_id>", methods=["POST"])
def remove_from_cart(product_id):

    cart = session.get("cart", {})

    product_key = str(product_id)

    if product_key in cart:
        del cart[product_key]

    session["cart"] = cart

    return redirect("/cart")


# ================= UPDATE CART =================

@app.route("/update-cart/<int:product_id>/<action>", methods=["POST"])
def update_cart(product_id, action):

    cart = session.get("cart", {})

    product_key = str(product_id)

    if product_key not in cart:
        return redirect("/cart")

    conn = get_db()

    product = conn.execute(
        "SELECT stock FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    conn.close()

    if product is None:

        cart.pop(product_key, None)

    elif action == "increase":

        if cart[product_key] < product["stock"]:
            cart[product_key] += 1

    elif action == "decrease":

        cart[product_key] -= 1

        if cart[product_key] <= 0:
            cart.pop(product_key)

    session["cart"] = cart

    return redirect("/cart")


# ================= CHECKOUT =================

@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():

    cart = session.get("cart", {})

    if not cart:
        return redirect("/cart")

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name or not phone or not address:
            return "Please fill all delivery fields.", 400

        conn = get_db()

        try:

            total = 0
            order_items = []

            # Step 1: Check products and stock

            for product_id, quantity in cart.items():

                quantity = int(quantity)

                if quantity <= 0:
                    raise ValueError("Invalid cart quantity.")

                product = conn.execute(
                    "SELECT * FROM products WHERE id = ?",
                    (product_id,)
                ).fetchone()

                if product is None:
                    raise ValueError("Product not found.")

                if quantity > product["stock"]:
                    raise ValueError(
                        f"Not enough stock for {product['name']}."
                    )

                total += product["price"] * quantity

                order_items.append((
                    product_id,
                    product["name"],
                    quantity,
                    product["price"]
                ))

            # Step 2: Create order

            cursor = conn.execute(
                """
                INSERT INTO orders
                (customer_id, customer_name, phone, address, total, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session["user_id"],
                    name,
                    phone,
                    address,
                    total,
                    "Pending"
                )
            )

            order_id = cursor.lastrowid

            # Step 3: Save order items and update stock

            for product_id, product_name, quantity, unit_price in order_items:

                conn.execute(
                    """
                    INSERT INTO order_items
                    (order_id, product_id, product_name, quantity, unit_price)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        product_id,
                        product_name,
                        quantity,
                        unit_price
                    )
                )

                stock_update = conn.execute(
                    """
                    UPDATE products
                    SET stock = stock - ?
                    WHERE id = ? AND stock >= ?
                    """,
                    (quantity, product_id, quantity)
                )

                if stock_update.rowcount != 1:
                    raise ValueError(
                        f"Stock changed for {product_name}. Please try again."
                    )

            # Step 4: Save order

            conn.commit()

            session["cart"] = {}

            return (
                f"Order placed successfully! Order ID: {order_id}"
            )

        except Exception as error:

            conn.rollback()

            return str(error), 400

        finally:

            conn.close()

    return render_template("checkout.html")


# ================= PROFILE =================

@app.route("/profile")
def profile():

    if "user_id" not in session:
        return render_template("profile.html", user=None)

    conn = get_db()

    user = conn.execute(
        "SELECT id, name, email FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    conn.close()

    if user is None:

        session.clear()

        return render_template(
            "profile.html",
            user=None
        )

    return render_template(
        "profile.html",
        user=user
    )


# ================= MY ORDERS =================

@app.route("/my-orders")
@login_required
def my_orders():

    conn = get_db()

    orders = conn.execute(
        """
        SELECT * FROM orders
        WHERE customer_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    order_details = []

    for order in orders:

        items = conn.execute(
            "SELECT * FROM order_items WHERE order_id = ?",
            (order["id"],)
        ).fetchall()

        order_details.append({
            "order": order,
            "items": items
        })

    conn.close()

    return render_template(
        "my_orders.html",
        orders=order_details
    )


# ================= RUN APP =================

if __name__ == "__main__":
    app.run(debug=True)
