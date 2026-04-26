"""
tools/create_user.py
─────────────────────────────────────────────────────────────────────────────
Script untuk membuat hash password user yang dimasukkan ke .env

Cara pakai:
    python tools/create_user.py

Output: tempelkan ke USERS= di file .env
─────────────────────────────────────────────────────────────────────────────
"""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def main():
    print("=== Buat User untuk Stock Analysis Web ===\n")
    users = []
    while True:
        username = input("Username (kosongkan untuk selesai): ").strip()
        if not username:
            break
        password = input(f"Password untuk '{username}': ").strip()
        if not password:
            print("Password tidak boleh kosong, skip.\n")
            continue
        hashed = pwd_context.hash(password)
        users.append(f"{username}:{hashed}")
        print(f"✓ User '{username}' ditambahkan\n")

    if not users:
        print("Tidak ada user dibuat.")
        return

    result = ",".join(users)
    print("\n" + "="*60)
    print("Tempelkan baris ini ke file backend/.env:\n")
    print(f"USERS={result}")
    print("="*60)


if __name__ == "__main__":
    main()
