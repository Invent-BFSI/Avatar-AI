# app.py
import os
import logging
import pyodbc
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import AzureOpenAI
from dotenv import load_dotenv
import mysql.connector

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

# ---- FastAPI setup ----
origins = ["http://127.0.0.1:5500", "http://localhost:5500"]
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,          # set True only if you use cookies/auth
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],

)



class Payload(BaseModel):
    text: str
    user_id: str

# ---- Azure OpenAI config ----
AOAI_ENDPOINT   = os.environ.get("AZURE_OPENAI_ENDPOINT")
AOAI_API_KEY    = os.environ.get("AZURE_OPENAI_API_KEY")
AOAI_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
AOAI_API_VER    = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")

client = AzureOpenAI(
    azure_endpoint=AOAI_ENDPOINT or "",
    api_key=AOAI_API_KEY or "",
    api_version=AOAI_API_VER
)

# ---- DB connection ----


def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        database=os.getenv("DB_NAME"),
        ssl_ca=os.getenv("DB_SSL_CA")
    )


def upsert_customer_profile(profile):
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
    INSERT INTO customer_profile (
        customer_id, first_name, last_name, account_type, customer_type, address, phone_number, ssn_masked,
        portfolio_status, relationships, retail_banking_product, email_id,
        monthly_inflow, monthly_outflow, total_debt, risk_appetite, preferred_sector,
        investment_amount, investment_period, future_goals
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        first_name=VALUES(first_name),
        last_name=VALUES(last_name),
        account_type=VALUES(account_type),
        customer_type=VALUES(customer_type),
        address=VALUES(address),
        phone_number=VALUES(phone_number),
        ssn_masked=VALUES(ssn_masked),
        portfolio_status=VALUES(portfolio_status),
        relationships=VALUES(relationships),
        retail_banking_product=VALUES(retail_banking_product),
        email_id=VALUES(email_id),
        monthly_inflow=VALUES(monthly_inflow),
        monthly_outflow=VALUES(monthly_outflow),
        total_debt=VALUES(total_debt),
        risk_appetite=VALUES(risk_appetite),
        preferred_sector=VALUES(preferred_sector),
        investment_amount=VALUES(investment_amount),
        investment_period=VALUES(investment_period),
        future_goals=VALUES(future_goals);
    """

    values = (
        profile.get("customer_id"),
        profile.get("first_name"), profile.get("last_name"),
        profile.get("account_type"), profile.get("customer_type"),
        profile.get("address"), profile.get("phone_number"),
        profile.get("ssn_masked"), profile.get("portfolio_status"),
        profile.get("relationships"), profile.get("retail_banking_product"),
        profile.get("email_id"), profile.get("monthlyInflow"),
        profile.get("monthlyOutflow"), profile.get("totalDebt"),
        profile.get("riskAppetite"), profile.get("preferredSector"),
        profile.get("investmentAmount"), profile.get("investmentPeriod"),
        profile.get("futureGoals")
    )

    cursor.execute(sql, values)
    conn.commit()
    cursor.close()
    conn.close()

# ---- Conversation State Machine ----
conversation_state = {}

class InnoviyaBot:
    steps = [
        "ask_name", "ask_city", "ask_inflow", "ask_outflow",
        "ask_liabilities", "ask_risk", "ask_sector",
        "ask_goals", "ask_period", "final_strategy"
    ]

    def __init__(self, user_id):
        self.user_id = user_id
        if user_id not in conversation_state:
            conversation_state[user_id] = {"step": 0, "profile": {}}
        self.state = conversation_state[user_id]

    def next_step(self, user_input):
        step = self.steps[self.state["step"]]
        handler = getattr(self, step)
        reply = handler(user_input)
        return reply

    def ask_name(self, user_input):
        if user_input:
            parts = user_input.split()
            self.state["profile"]["first_name"] = parts[0]
            self.state["profile"]["last_name"] = parts[-1] if len(parts) > 1 else None
            self.state["profile"]["customer_id"] = f"CUST-{self.user_id}"
            upsert_customer_profile(self.state["profile"])
            self.state["step"] += 1
            return f"It's a pleasure to meet you {parts[0]}. Which city are you joining from today?"
        return "Hello! I'm Innoviya, your financial consultant. May I please have your name?"

    def ask_city(self, user_input):
        self.state["profile"]["address"] = user_input
        upsert_customer_profile(self.state["profile"])
        self.state["step"] += 1
        return f"Alright, {self.state['profile']['first_name']}. {user_input}, a fantastic city! Could you share your average monthly cash inflow?"

    def ask_inflow(self, user_input):
        self.state["profile"]["monthlyInflow"] = self._extract_number(user_input)
        upsert_customer_profile(self.state["profile"])
        self.state["step"] += 1
        return f"Thank you {self.state['profile']['first_name']}. So, your monthly cash inflow is {self.state['profile']['monthlyInflow']}. Now, what is your average monthly cash outflow?"

    def ask_outflow(self, user_input):
        self.state["profile"]["monthlyOutflow"] = self._extract_number(user_input)
        upsert_customer_profile(self.state["profile"])
        self.state["step"] += 1
        return f"Understood. So your monthly cash outflow is {self.state['profile']['monthlyOutflow']}. Do you have any liabilities?"

    def ask_liabilities(self, user_input):
        self.state["profile"]["totalDebt"] = self._extract_number(user_input)
        upsert_customer_profile(self.state["profile"])
        self.state["step"] += 1
        return "Let's talk about your risk appetite. Would you describe yourself as Conservative, Moderate, or Aggressive?"

    def ask_risk(self, user_input):
        self.state["profile"]["riskAppetite"] = user_input
        upsert_customer_profile(self.state["profile"])
        self.state["step"] += 1
        return "Do you have a preferred sector you're interested in, such as Tech, Healthcare, Finance, or Energy?"

    def ask_sector(self, user_input):
        self.state["profile"]["preferredSector"] = user_input
        upsert_customer_profile(self.state["profile"])
        self.state["step"] += 1
        return "Now, let's discuss your future goals. What are your financial goals for the future?"

    def ask_goals(self, user_input):
        self.state["profile"]["futureGoals"] = user_input
        upsert_customer_profile(self.state["profile"])
        self.state["step"] += 1
        return "How long would you like to invest for (in months)?"

    def ask_period(self, user_input):
        self.state["profile"]["investmentPeriod"] = self._extract_number(user_input)
        inflow = self.state["profile"].get("monthlyInflow", 0)
        outflow = self.state["profile"].get("monthlyOutflow", 0)
        self.state["profile"]["investmentAmount"] = inflow - outflow
        upsert_customer_profile(self.state["profile"])
        self.state["step"] += 1
        return "Thank you. I now have enough information to craft your personalized investment strategy."

    def final_strategy(self, user_input):
        risk = self.state["profile"].get("riskAppetite", "Moderate").lower()
        if "conservative" in risk:
            allocation = "Equity: 30% / Savings: 70%"
        elif "aggressive" in risk:
            allocation = "Equity: 80% / Savings: 20%"
        else:
            allocation = "Equity: 60% / Savings: 40%"
        self.state["profile"]["assetAllocation"] = allocation
        upsert_customer_profile(self.state["profile"])
        return f"Based on your profile, your asset allocation will be {allocation}. Thank you for sharing your details, {self.state['profile']['first_name']}."

    def _extract_number(self, text):
        import re
        nums = re.findall(r"\d+", text.replace(",", ""))
        return float(nums[0]) if nums else 0.0

# ---- FastAPI route ----
@app.post("/chat")
async def handle_chat(data: Payload):
    bot = InnoviyaBot(data.user_id)
    reply = bot.next_step(data.text.strip())
    return {"reply": reply}

----------------------------------------------


# 1. Mount the 'build' folder from your React project
# Assuming your structure is: root/frontend/build
app.mount("/", StaticFiles(directory="frontend/build", html=True), name="static")

# 2. Catch-all route to handle React Router (refreshing pages)
@app.exception_handler(404)
async def not_found_exception_handler(request, exc):
    return FileResponse("frontend/build/index.html")
