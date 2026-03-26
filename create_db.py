from app import app, db

def main():
    with app.app_context():
        db.create_all()
        print("Database tables created (sqlite: app.db or DATABASE_URL).")

if __name__ == "__main__":
    main()
