import subprocess
import secrets

import os
from cloudflare import Cloudflare
from dotenv import load_dotenv

load_dotenv()

MAMMOTH_USERS_GROUP = "mammoth_cluster_users"
CLOUDFLARE_ACCOUNT_ID = "5d55ab66bfc36f5ae67587f2fef416bb"
CLOUDFLARE_ACCESS_POLICY_ID = "eb65ea54-b71a-4855-8762-ecdbf6502dbe"
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")


# Create the unix mammoth user group if it doesn't exist
def create_unix_mammoth_group_if_not_exists():
    command = f"getent group {MAMMOTH_USERS_GROUP} || groupadd {MAMMOTH_USERS_GROUP}"
    subprocess.run(command, check=True, shell=True)
    print("Ensured mammoth user group exists")


# Function to create a unix user. Expects sanitized input.
def create_unix_user(username: str):
    # Generate a random password. Users cannot know their password or switch users.
    random_pass = secrets.token_hex(32)

    # Create the user in the mammoth cluster users
    command = f"useradd {username} -p {random_pass} -g {MAMMOTH_USERS_GROUP}"
    subprocess.run(command, check=True, shell=True)

    print(f"User {username} created successfully!")


# Function to list all unix users who are in the mammoth users group
def list_mammoth_unix_users() -> list[str]:
    mammoth_users: list[str] = []

    # Get a list of users mapped to their groups in the format
    # "username : group1 group2"
    command = "cat /etc/passwd | awk -F':' '{ print $1}' | xargs -n1 groups"
    result = subprocess.run(
        command, check=True, shell=True, capture_output=True, text=True
    )
    user_lines = result.stdout.splitlines()
    print("List of users:")
    for user_line in user_lines:
        # This user is part of the mammoth group
        if MAMMOTH_USERS_GROUP in user_line:
            user = user_line.split(" ")[0]
            mammoth_users.append(user)

    return mammoth_users


# Function to delete a user. Expects sanitized input.
def delete_user(username):
    command = f"userdel -r {username}"  # -r flag removes the user'
    # Use 'echo' to pass the password automatically
    subprocess.run(command, shell=True, check=True)
    print(f"User {username} deleted successfully!")


# Sync the list of users to the cloudflare access policy
def sync_cloudflare_access_policy(users: list[str]):
    client = Cloudflare(api_token=CLOUDFLARE_API_TOKEN)

    client.zero_trust.access.policies.update(
        name="Automatically Managed User Policy",
        policy_id=CLOUDFLARE_ACCESS_POLICY_ID,
        account_id=CLOUDFLARE_ACCOUNT_ID,
        include=[{"email": {"email": user + "@exeter.ac.uk"}} for user in users],
        decision="allow",
    )
    print(f"Successfully updated access policy")


def main():
    if os.geteuid() != 0:
        print("This script must be run as root")
        exit(1)

    if CLOUDFLARE_API_TOKEN == None or len(CLOUDFLARE_API_TOKEN) == 0:
        print("Specify a CLOUDFLARE_API_TOKEN environment variable")
        exit(1)

    create_unix_mammoth_group_if_not_exists()

    # Todo: Get list of users from somewhere
    new_users = ["sr996", "ww414"]

    # Get existing users
    existing_users = list_mammoth_unix_users()

    # Create users which need to be created
    for potential_new_user in new_users:
        if potential_new_user not in existing_users:
            # We don't currently have this user
            create_unix_user(potential_new_user)

    # Delete users which shouldn't exist
    for existing_user in existing_users:
        if existing_user not in new_users:
            # This user is not in the new users list
            delete_user(existing_user)

    # Sync the users to the cloudflare access policy
    sync_cloudflare_access_policy(new_users)


if __name__ == "__main__":
    main()
