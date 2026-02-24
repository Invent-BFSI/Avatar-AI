# app.py
import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AzureOpenAI
from dotenv import load_dotenv
import mysql.connector
from services.customer_service import build_profile_from_conversation
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
import pyodbc
from services.customer_service import build_profile_from_conversation


from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

# ---- FastAPI setup ----

origins = [
    "http://localhost:3000",  # React dev
    "https://invest-soul-adeagbcufyhhfxc2.eastus2-01.azurewebsites.net",  # your Azure Web App (make sure https)
    # add any custom domain here, e.g., "https://app.innoviya.ai"
]

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,                 # True only if you need cookies/auth
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
    # TODO: move to environment variables or Key Vault for production
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=your-server.database.windows.net;"
        "DATABASE=your-db;"
        "UID=your-user;"
        "PWD=your-password;"
        "Encrypt=yes;TrustServerCertificate=no;"
    )
    return conn




ef upsert_customer_profile(profile: dict):
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            sql = """
            EXEC dbo.UpsertCustomerProfile
                @customer_id = ?,
                @first_name = ?,
                @last_name = ?,
                @account_type = ?,
                @customer_type = ?,
                @address = ?,
                @phone_number = ?,
                @ssn_masked = ?,
                @portfolio_status = ?,
                @relationships = ?,
                @retail_banking_product = ?,
                @email_id = ?,
                @monthly_inflow = ?,
                @monthly_outflow = ?,
                @total_debt = ?,
                @risk_appetite = ?,
                @preferred_sector = ?,
                @investment_amount = ?,
                @investment_period = ?,
                @future_goals = ?;
            """
            params = (
                profile.get("customer_id"),
                profile.get("first_name"),
                profile.get("last_name"),
                profile.get("account_type"),
                profile.get("customer_type"),
                profile.get("address"),
                profile.get("phone_number"),
                profile.get("ssn_masked"),
                profile.get("portfolio_status"),
                profile.get("relationships"),
                profile.get("retail_banking_product"),
                profile.get("email_id"),
                profile.get("monthly_inflow"),
                profile.get("monthly_outflow"),
                profile.get("total_debt"),
                profile.get("risk_appetite"),
                profile.get("preferred_sector"),
                profile.get("investment_amount"),
                profile.get("investment_period"),
                profile.get("future_goals"),
            )
            cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


# ---- Conversation State Machine ----
conversation_state = {}

class ConversationPayload(BaseModel):
    customer_id: str = Field(..., min_length=1)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    account_type: Optional[str] = None
    customer_type: Optional[str] = None
    address: Optional[str] = None
    phone_number: Optional[str] = None
    ssn_masked: Optional[str] = None
    portfolio_status: Optional[str] = None
    relationships: Optional[str] = None
    retail_banking_product: Optional[str] = None
    email_id: Optional[EmailStr] = None
    monthly_inflow: Optional[float] = None
    monthly_outflow: Optional[float] = None
    total_debt: Optional[float] = None
    risk_appetite: Optional[str] = None
    preferred_sector: Optional[str] = None
    investment_amount: Optional[float] = None
    investment_period: Optional[int] = None
    future_goals: Optional[str] = None

class UpsertResponse(BaseModel):
    status: str
    customer_id: str

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



@app.post("/conversation/upsert-profile", response_model=UpsertResponse)
def upsert_profile_from_conversation(payload: ConversationPayload):
    """
    Accepts a conversation payload, normalizes it to profile fields,
    and upserts into SQL Server via stored procedure.
    """
    try:
        profile = build_profile_from_conversation(payload.model_dump())
        upsert_customer_profile(profile)
        return UpsertResponse(status="ok", customer_id=profile["customer_id"])
    except pyodbc.Error as e:
        # Include SQLSTATE/Native error for debugging if needed, but avoid leaking secrets
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Optional: basic health check
@app.get("/healthz")
def health():
    return {"status": "up"}


# 1. Mount the 'build' folder from your React project
# Assuming your structure is: root/frontend/build
app.mount("/", StaticFiles(directory="frontend/build", html=True), name="static")

# 2. Catch-all route to handle React Router (refreshing pages)
@app.exception_handler(404)
async def not_found_exception_handler(request, exc):
    return FileResponse("frontend/build/index.html")
