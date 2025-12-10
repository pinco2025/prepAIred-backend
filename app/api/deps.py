from typing import Generator
from app.core.security import get_current_user, TokenData
from fastapi import Depends

# Since Supabase client is a singleton and handles connection internally,
# we usually don't need a dependency for "get_db" like in SQLModel/SQLAlchemy
# unless we want to inject specific sessions.
# But for Supabase, we interact via the client directly.
# However, if we want to enforce RLS (Row Level Security) on the server side using the user's token,
# we would need to pass the JWT to the supabase client.
# The 'supabase-py' client initialized with SERVICE_ROLE key bypasses RLS.
# The one initialized with ANON key respects RLS but acts as anon unless we set the session.

# If we want to use the user's token to respect RLS:
# We might need to create a new client instance or set auth for the request.
# But standard practice in many backends using Supabase as a wrapper is to just use the Service Key (admin access)
# and handle authorization in the backend code (Service Layer),
# OR use the user's token to forward requests.

# For this boilerplate, I will demonstrate using the Service Key for admin tasks (or generic backend tasks)
# AND parsing the user from the token for context.

async def get_current_active_user(
    current_user: TokenData = Depends(get_current_user),
) -> TokenData:
    # Here you could check if the user is active in your database if needed
    return current_user
