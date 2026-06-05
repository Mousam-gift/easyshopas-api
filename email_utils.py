from fastapi import (BackgroundTasks, UploadFile, File, Form, HTTPException, status)
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
#from dotenv import dotenv_values
from pydantic import BaseModel, EmailStr
from typing import List
from models import User
import jwt





#config_credentials = dotenv_values(".env")

import os

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
SECRET = os.getenv("SECRET")




conf = ConnectionConfig(
    MAIL_USERNAME=EMAIL,
    MAIL_PASSWORD=PASSWORD,
    MAIL_FROM=EMAIL,
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True
)



async def send_email(email: List, instance: User):
    token_data = {
        "id": instance.id,
        "username": instance.username,
        "email": instance.email
    }

    token = jwt.encode(token_data, SECRET, algorithm='HS256')
    

    template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Email Verification</title>
    </head>
    <body>
        <div style = "display: flex; align-items: center; justify-content: center; flex-direction: column">
            <h3>Account Verification</h3>
            <br>
            <p>Thanks for choosing our service! Please click the button below to verify your email</p>
            <a style="margin-top:1rem; padding:1rem; border-radius:0.5rem; font-size:1rem;text-decoration:none; background:#0275d8; color:white;" href="https://YOUR-APP.up.railway.app/verification/?token={token}">Verify your Email</a>

            <p>Please ignore this email if you did not register for EasyShopas and nothing will happen. Thanks</p>
        </div>
    </body>
    </html>
    """

    message = MessageSchema(
        subject="Easyshopas account Verification email",
        recipients=email,
        body = template,
        subtype="html"
    )

    fm = FastMail(conf)
    await fm.send_message(message=message)