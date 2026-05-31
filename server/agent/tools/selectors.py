SELECTORS = {
    "login": {
        "email_input": "[type='email'], input[name='email'], input[name='username']",
        "password_input": "[type='password'], input[name='password']",
        "submit_button": "button[type='submit'], input[type='submit'], #login-btn",
    },
    "gov_portal": {
        "email_input": "#user_email",
        "password_input": "#user_password",
        "submit_button": "#sign_in_button",
    },
    "general": {
        "search_input": "input[type='search'], [name='q']",
    }
}

def get_selector(category: str, element: str) -> str | None:
    return SELECTORS.get(category, {}).get(element)
