OWNER_ADMIN_EMAIL='elsadianri10@gmail.com'
def is_owner_email(email):
    return isinstance(email,str) and email.strip().casefold()==OWNER_ADMIN_EMAIL
