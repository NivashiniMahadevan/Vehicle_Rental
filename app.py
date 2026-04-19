from flask import Flask, flash, redirect, render_template, request, url_for
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = "secret123"

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root123",
    database="vehicle_rental_db",
    auth_plugin="mysql_native_password",
)


def fetch_rows(query, params=None):
    cursor = db.cursor()
    cursor.execute(query, params or ())
    return cursor.fetchall()


def fetch_value(query, default=0):
    try:
        data = fetch_rows(query)
        return data[0][0] if data and data[0] and data[0][0] is not None else default
    except Error:
        return default


def fetch_rows_safe(query, fallback=None, params=None):
    try:
        return fetch_rows(query, params=params)
    except Error:
        return fallback or []


@app.route("/")
def home():
    total_vehicles = fetch_value("SELECT COUNT(*) FROM VEHICLE")
    total_bookings = fetch_value("SELECT COUNT(*) FROM BOOKING")
    total_customers = fetch_value("SELECT COUNT(*) FROM CUSTOMER")
    active_rentals = fetch_value("SELECT COUNT(*) FROM BOOKING WHERE status IN ('Active', 'Confirmed')")
    revenue_total = fetch_value("SELECT COALESCE(SUM(amount), 0) FROM PAYMENT WHERE payment_status IN ('Paid', 'Completed')", 0)

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    booking_month_rows = fetch_rows_safe(
        """
        SELECT MONTH(start_date) AS month_no, COUNT(*)
        FROM BOOKING
        WHERE YEAR(start_date) = YEAR(CURDATE())
        GROUP BY MONTH(start_date)
        """
    )
    booking_by_month = {int(row[0]): int(row[1]) for row in booking_month_rows}
    raw_booking_values = [booking_by_month.get(i, 0) for i in range(1, 13)]
    max_bookings = max(raw_booking_values) if raw_booking_values else 0
    booking_percentages = [round((value / max_bookings) * 100, 2) if max_bookings else 0 for value in raw_booking_values]

    revenue_month_rows = fetch_rows_safe(
        """
        SELECT MONTH(payment_date) AS month_no, COALESCE(SUM(amount), 0)
        FROM PAYMENT
        WHERE YEAR(payment_date) = YEAR(CURDATE())
        GROUP BY MONTH(payment_date)
        """
    )
    revenue_by_month = {int(row[0]): float(row[1]) for row in revenue_month_rows}
    raw_revenue_values = [revenue_by_month.get(i, 0.0) for i in range(1, 13)]
    max_revenue = max(raw_revenue_values) if raw_revenue_values else 0
    revenue_percentages = [round((value / max_revenue) * 100, 2) if max_revenue else 0 for value in raw_revenue_values]

    rented_vehicles = fetch_value("SELECT COUNT(*) FROM VEHICLE WHERE status = 'Rented'")
    utilization_rate = round((rented_vehicles / total_vehicles) * 100, 2) if total_vehicles else 0
    upcoming_returns = fetch_rows_safe(
        """
        SELECT r.rental_id, c.name, CONCAT(v.model, ' (', v.reg_no, ')'), r.return_date
        FROM RENTAL r
        JOIN BOOKING b ON b.booking_id = r.booking_id
        JOIN CUSTOMER c ON c.customer_id = b.customer_id
        JOIN VEHICLE v ON v.vehicle_id = b.vehicle_id
        WHERE r.return_date IS NOT NULL AND r.return_date >= CURDATE()
        ORDER BY r.return_date ASC, r.rental_id ASC
        LIMIT 8
        """
    )

    return render_template(
        "index.html",
        total_vehicles=total_vehicles,
        total_bookings=total_bookings,
        total_customers=total_customers,
        active_rentals=active_rentals,
        revenue_total=revenue_total,
        month_labels=month_labels,
        booking_percentages=booking_percentages,
        revenue_percentages=revenue_percentages,
        utilization_rate=utilization_rate,
        upcoming_returns=upcoming_returns,
    )


@app.route("/vehicles")
def vehicles():
    selected_status = request.args.get("status", "All Status")
    allowed_statuses = {"All Status", "Available", "Rented", "Maintenance"}
    if selected_status not in allowed_statuses:
        selected_status = "All Status"

    if selected_status == "All Status":
        query = "SELECT vehicle_id, reg_no, brand, model, status, year, mileage FROM VEHICLE ORDER BY vehicle_id ASC"
        data = fetch_rows_safe(query)
    else:
        query = """
        SELECT vehicle_id, reg_no, brand, model, status, year, mileage
        FROM VEHICLE
        WHERE status = %s
        ORDER BY vehicle_id ASC
        """
        data = fetch_rows_safe(query, params=(selected_status,))

    return render_template("vehicles.html", vehicles=data, selected_status=selected_status)


@app.route("/customers")
def customers():
    data = fetch_rows_safe(
        """
        SELECT customer_id, name, phone, COALESCE(email, ''), license_no, COALESCE(address, '')
        FROM CUSTOMER
        ORDER BY customer_id ASC
        """
    )
    return render_template("customers.html", customers=data)


@app.route("/bookings")
def bookings():
    customers_data = fetch_rows_safe("SELECT customer_id, name FROM CUSTOMER")
    vehicles_data = fetch_rows_safe("SELECT vehicle_id, reg_no, model FROM VEHICLE")
    bookings_data = fetch_rows_safe(
        """
        SELECT b.booking_id, c.name, CONCAT(v.model, ' (', v.reg_no, ')'), b.start_date, b.end_date, b.status
        FROM BOOKING b
        JOIN CUSTOMER c ON c.customer_id = b.customer_id
        JOIN VEHICLE v ON v.vehicle_id = b.vehicle_id
        ORDER BY b.booking_id ASC
        """
    )

    return render_template(
        "bookings.html",
        customers=customers_data,
        vehicles=vehicles_data,
        bookings=bookings_data,
    )


@app.route("/rentals")
def rentals():
    active_rentals = fetch_rows_safe(
        """
        SELECT b.booking_id, c.name, CONCAT(v.model, ' (', v.reg_no, ')'), b.start_date, b.end_date, b.status
        FROM BOOKING b
        JOIN CUSTOMER c ON c.customer_id = b.customer_id
        JOIN VEHICLE v ON v.vehicle_id = b.vehicle_id
        WHERE b.status IN ('Active', 'Confirmed', 'Overdue')
        ORDER BY b.booking_id ASC
        """
    )

    completed_rentals = fetch_rows_safe(
        """
        SELECT b.booking_id, c.name, CONCAT(v.model, ' (', v.reg_no, ')'), b.start_date, b.end_date, b.status
        FROM BOOKING b
        JOIN CUSTOMER c ON c.customer_id = b.customer_id
        JOIN VEHICLE v ON v.vehicle_id = b.vehicle_id
        WHERE b.status IN ('Completed', 'Closed')
        ORDER BY b.booking_id ASC
        """
    )

    overdue_count = sum(1 for row in active_rentals if len(row) > 5 and str(row[5]).lower() == "overdue")

    return render_template(
        "rentals.html",
        active_rentals=active_rentals,
        completed_rentals=completed_rentals,
        overdue_count=overdue_count,
    )


@app.route("/payments")
def payments():
    payment_rows = fetch_rows_safe(
        """
        SELECT p.payment_id, p.rental_id, p.amount, p.payment_date, p.payment_mode, p.payment_status
        FROM PAYMENT p
        ORDER BY p.payment_id ASC
        """
    )

    total_paid = fetch_value(
        "SELECT COALESCE(SUM(amount), 0) FROM PAYMENT WHERE payment_status IN ('Paid', 'Completed')", 0
    )
    pending_amount = fetch_value("SELECT COALESCE(SUM(amount), 0) FROM PAYMENT WHERE payment_status = 'Pending'", 0)
    total_transactions = fetch_value("SELECT COUNT(*) FROM PAYMENT", 0)
    rental_options = fetch_rows_safe("SELECT rental_id FROM RENTAL ORDER BY rental_id ASC")

    return render_template(
        "payments.html",
        payments=payment_rows,
        total_paid=total_paid,
        pending_amount=pending_amount,
        total_transactions=total_transactions,
        rental_options=rental_options,
    )


@app.route("/maintenance")
def maintenance():
    maintenance_rows = fetch_rows_safe(
        """
        SELECT maintenance_id, vehicle_id, description, maintenance_date, cost, status
        FROM MAINTENANCE
        ORDER BY maintenance_id ASC
        """
    )
    in_service = fetch_value("SELECT COUNT(*) FROM MAINTENANCE WHERE status = 'In Service'", 0)
    scheduled = fetch_value("SELECT COUNT(*) FROM MAINTENANCE WHERE status = 'Scheduled'", 0)
    completed = fetch_value("SELECT COUNT(*) FROM MAINTENANCE WHERE status = 'Completed'", 0)
    total_cost = fetch_value("SELECT COALESCE(SUM(cost), 0) FROM MAINTENANCE", 0)
    vehicle_options = fetch_rows_safe("SELECT vehicle_id, reg_no, model FROM VEHICLE ORDER BY vehicle_id ASC")

    return render_template(
        "maintenance.html",
        maintenance_rows=maintenance_rows,
        in_service=in_service,
        scheduled=scheduled,
        completed=completed,
        total_cost=total_cost,
        vehicle_options=vehicle_options,
    )


@app.route("/fleet-lifecycle")
def fleet_lifecycle():
    lifecycle_rows = fetch_rows_safe(
        """
        SELECT
            v.vehicle_id,
            v.reg_no,
            v.model,
            fl.purchase_date,
            CASE
                WHEN fl.resale_date IS NOT NULL THEN 'Retired'
                WHEN LOWER(COALESCE(v.status, '')) = 'retired' THEN 'Retired'
                WHEN LOWER(COALESCE(v.status, '')) = 'maintenance' THEN 'Maintenance'
                WHEN LOWER(COALESCE(v.status, '')) IN ('available', 'rented', 'active') THEN 'Active'
                ELSE 'Purchased'
            END AS lifecycle_stage,
            COALESCE(v.status, 'Unknown') AS current_status
        FROM VEHICLE v
        LEFT JOIN fleet_lifecycle fl ON fl.vehicle_id = v.vehicle_id
        ORDER BY v.vehicle_id ASC
        """
    )

    purchased_count = len([row for row in lifecycle_rows if row[4] == "Purchased"])
    active_count = len([row for row in lifecycle_rows if row[4] == "Active"])
    maintenance_count = len([row for row in lifecycle_rows if row[4] == "Maintenance"])
    retired_count = len([row for row in lifecycle_rows if row[4] == "Retired"])

    return render_template(
        "fleet_lifecycle.html",
        lifecycle_rows=lifecycle_rows,
        purchased_count=purchased_count,
        active_count=active_count,
        maintenance_count=maintenance_count,
        retired_count=retired_count,
    )


@app.route("/add_booking", methods=["POST"])
def add_booking():
    cursor = db.cursor()

    customer_id = request.form["customer_id"]
    vehicle_id = request.form["vehicle_id"]
    start_date = request.form["start_date"]
    end_date = request.form["end_date"]

    query = """
    INSERT INTO BOOKING (customer_id, vehicle_id, booking_date, start_date, end_date, status)
    VALUES (%s, %s, CURDATE(), %s, %s, 'Confirmed')
    """

    cursor.execute(query, (customer_id, vehicle_id, start_date, end_date))
    db.commit()

    flash("Booking added successfully!")
    return redirect(url_for("bookings"))


@app.route("/add_customer", methods=["POST"])
def add_customer():
    try:
        cursor = db.cursor()
        name = request.form["name"]
        phone = request.form["phone"]
        email = request.form.get("email") or None
        license_no = request.form["license_no"]
        address = request.form.get("address") or None

        cursor.execute(
            """
            INSERT INTO CUSTOMER (name, phone, email, license_no, address)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (name, phone, email, license_no, address),
        )
        db.commit()
        flash("Customer added successfully!")
    except Error as exc:
        flash(f"Unable to add customer: {exc}")
    return redirect(url_for("customers"))


@app.route("/add_vehicle", methods=["POST"])
def add_vehicle():
    try:
        cursor = db.cursor()
        reg_no = request.form["reg_no"]
        brand = request.form["brand"]
        model = request.form["model"]
        year = request.form.get("year") or None
        mileage = request.form.get("mileage") or None
        status = request.form["status"]

        cursor.execute(
            """
            INSERT INTO VEHICLE (reg_no, brand, model, year, mileage, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (reg_no, brand, model, year, mileage, status),
        )
        db.commit()
        flash("Vehicle added successfully!")
    except Error as exc:
        flash(f"Unable to add vehicle: {exc}")
    return redirect(url_for("vehicles"))


@app.route("/add_payment", methods=["POST"])
def add_payment():
    try:
        cursor = db.cursor()
        rental_id = request.form["rental_id"]
        amount = request.form["amount"]
        payment_date = request.form["payment_date"]
        payment_mode = request.form["payment_mode"]
        payment_status = request.form["payment_status"]

        cursor.execute(
            """
            INSERT INTO PAYMENT (rental_id, amount, payment_date, payment_mode, payment_status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (rental_id, amount, payment_date, payment_mode, payment_status),
        )
        db.commit()
        flash("Payment added successfully!")
    except Error as exc:
        flash(f"Unable to add payment: {exc}")
    return redirect(url_for("payments"))


@app.route("/add_maintenance", methods=["POST"])
def add_maintenance():
    try:
        cursor = db.cursor()
        vehicle_id = request.form["vehicle_id"]
        maintenance_date = request.form["maintenance_date"]
        description = request.form["description"]
        cost = request.form["cost"]
        status = request.form["status"]

        cursor.execute(
            """
            INSERT INTO MAINTENANCE (vehicle_id, maintenance_date, description, cost, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (vehicle_id, maintenance_date, description, cost, status),
        )
        db.commit()
        flash("Maintenance record added successfully!")
    except Error as exc:
        flash(f"Unable to add maintenance record: {exc}")
    return redirect(url_for("maintenance"))


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)