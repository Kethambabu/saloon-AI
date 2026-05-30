from db.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Query the database to see what enum values exist
    result = conn.execute(text("""
        SELECT enumlabel 
        FROM pg_enum 
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'user_role')
    """)).fetchall()
    print('Database user_role enum values:')
    for row in result:
        print(f'  - {row[0]}')
    
    # Also check existing user roles
    users = conn.execute(text("SELECT email, role FROM users")).fetchall()
    print('\nExisting users and their roles:')
    for user in users:
        print(f'  - {user[0]}: {user[1]}')
