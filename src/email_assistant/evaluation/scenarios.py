"""10 unique test scenarios with human reference emails for evaluation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TestScenario(BaseModel):
    id: str = Field(..., description="Unique scenario identifier")
    intent: str = Field(..., description="The core purpose of the email")
    key_facts: list[str] = Field(..., description="Key facts to include")
    tone: str = Field(..., description="Desired tone")
    reference_subject: str = Field(..., description="Human-written reference subject")
    reference_body: str = Field(..., description="Human-written reference body")


TEST_SCENARIOS: list[TestScenario] = [
    TestScenario(
        id="scenario_01",
        intent="Follow up after a networking event",
        key_facts=["Met at Tech Conference 2026", "Discussed potential collaboration on AI project", "Available for coffee chat next week"],
        tone="professional",
        reference_subject="Great Meeting You at Tech Conference 2026",
        reference_body="Dear Alex,\n\nIt was a pleasure meeting you at Tech Conference 2026 last week. I truly enjoyed our conversation about the potential collaboration on the AI project we discussed.\n\nI believe there is strong alignment between our teams, and I would welcome the opportunity to explore this further. I am available for a coffee chat next week at your convenience — perhaps Tuesday or Wednesday afternoon?\n\nLooking forward to continuing our discussion.\n\nBest regards,\nJordan",
    ),
    TestScenario(
        id="scenario_02",
        intent="Request budget approval for Q3 marketing campaign",
        key_facts=["Campaign budget is $50,000", "Expected ROI is 3x", "Targets 10,000 new leads"],
        tone="formal",
        reference_subject="Q3 Marketing Campaign — Budget Approval Request",
        reference_body="Dear Ms. Chen,\n\nI am writing to formally request your approval for the Q3 marketing campaign budget allocation.\n\nThe proposed campaign requires an investment of $50,000. Based on our market analysis and historical performance data, we project a return on investment of 3x within the quarter. This initiative is expected to generate approximately 10,000 new qualified leads.\n\nI have attached the detailed campaign plan and financial projections for your review.\n\nThank you for your consideration.\n\nSincerely,\nMarketing Department",
    ),
    TestScenario(
        id="scenario_03",
        intent="Invite colleague to team lunch",
        key_facts=["New Italian restaurant downtown", "Friday at noon", "Celebrating project completion"],
        tone="casual",
        reference_subject="Team lunch this Friday?",
        reference_body="Hey Sam!\n\nJust wanted to check — there's a new Italian place downtown that looks amazing. Want to grab lunch there this Friday around noon? We've been crushing it on the project lately and it'd be great to celebrate.\n\nLet me know if you're in!\n\nCheers,\nAlex",
    ),
    TestScenario(
        id="scenario_04",
        intent="Notify team of critical production issue",
        key_facts=["Payment service is down", "Affecting 30% of transactions", "Need all hands on deck"],
        tone="urgent",
        reference_subject="URGENT: Payment Service Outage — Immediate Action Required",
        reference_body="Team,\n\nWe are currently experiencing a critical outage in our payment service that is impacting approximately 30% of all transactions. This requires immediate attention from all available engineers.\n\nPlease join the incident bridge call at once and prioritize this issue above all other tasks.\n\nThis is our top priority.\n\nEngineering Lead",
    ),
    TestScenario(
        id="scenario_05",
        intent="Respond to customer complaint about delayed shipment",
        key_facts=["Order was delayed by 2 weeks", "Full refund is being processed", "Improved logistics measures are in place"],
        tone="empathetic",
        reference_subject="We're Sorry — Your Order Update and Refund",
        reference_body="Dear Sarah,\n\nI completely understand your frustration with the delay in receiving your order. Waiting two weeks beyond the promised delivery date is unacceptable, and I sincerely apologize for the inconvenience this has caused you.\n\nYour full refund has been processed and you should see it reflected in your account within 3-5 business days. Additionally, we have implemented improved logistics measures to prevent similar delays in the future.\n\nYour experience matters deeply to us.\n\nWith sincere apologies,\nCustomer Support Team",
    ),
    TestScenario(
        id="scenario_06",
        intent="Propose a new remote work policy",
        key_facts=["Productivity increased 15% during remote work trial", "Employee satisfaction scores improved by 20%", "Office costs could be reduced by 30% with hybrid model"],
        tone="professional",
        reference_subject="Proposal: Hybrid Remote Work Policy",
        reference_body="Dear Leadership Team,\n\nI am writing to propose the adoption of a hybrid remote work policy based on the results of our recent trial period.\n\nDuring the remote work trial, we observed a 15% increase in overall productivity and a 20% improvement in employee satisfaction scores. Additionally, transitioning to a hybrid model would allow us to reduce office-related costs by approximately 30%.\n\nI recommend a structured approach: three days remote, two days in-office.\n\nBest regards,\nHR Director",
    ),
    TestScenario(
        id="scenario_07",
        intent="Follow up on an unpaid invoice",
        key_facts=["Invoice #INV-2024-0892 is 30 days overdue", "Amount owed is $4,500", "Payment terms are Net 30"],
        tone="professional",
        reference_subject="Reminder: Overdue Invoice #INV-2024-0892",
        reference_body="Dear Accounts Payable,\n\nI hope this message finds you well. I am writing to follow up on invoice #INV-2024-0892, which is now 30 days past due.\n\nThe outstanding amount is $4,500 for services rendered per our agreed payment terms of Net 30. I have attached a copy of the original invoice for your reference.\n\nCould you please confirm the status of this payment?\n\nBest regards,\nFinance Team",
    ),
    TestScenario(
        id="scenario_08",
        intent="Congratulate team on successful product launch",
        key_facts=["Product launched on schedule", "First week sales exceeded targets by 40%", "Customer feedback has been overwhelmingly positive"],
        tone="enthusiastic",
        reference_subject="Incredible Launch — You All Made It Happen!",
        reference_body="Hi Team,\n\nI wanted to take a moment to congratulate each and every one of you on an absolutely phenomenal product launch!\n\nWe hit our launch date on schedule, and the results speak for themselves: first week sales have exceeded our targets by an impressive 40%. The customer feedback we've received has been overwhelmingly positive.\n\nThis achievement is a testament to your hard work and dedication.\n\nWith gratitude,\nProduct Lead",
    ),
    TestScenario(
        id="scenario_09",
        intent="Request meeting to discuss partnership opportunity",
        key_facts=["Potential partnership between TechCo and InnovateLab", "Synergies in AI and machine learning capabilities", "Target timeline is Q4 2026"],
        tone="formal",
        reference_subject="Partnership Discussion — TechCo and InnovateLab",
        reference_body="Dear Dr. Williams,\n\nI hope this letter finds you well. I am writing on behalf of TechCo to explore a potential partnership with InnovateLab.\n\nOur analysis has identified significant synergies between our respective AI and machine learning capabilities. We are targeting Q4 2026 for any formalized arrangement.\n\nWould you be available for an introductory call during the week of June 23rd?\n\nKind regards,\nVP of Business Development\nTechCo",
    ),
    TestScenario(
        id="scenario_10",
        intent="Apologize for a service outage affecting customers",
        key_facts=["Database outage lasted 4 hours yesterday", "Root cause was a failed migration script", "Monitoring and safeguards have been improved"],
        tone="empathetic",
        reference_subject="Our Apology — Yesterday's Service Disruption",
        reference_body="Dear Valued Customer,\n\nI am writing to personally apologize for the service disruption you experienced yesterday. Our database was unavailable for approximately four hours, and I understand how frustrating this was for you.\n\nThe root cause was a failed migration script. We have implemented enhanced monitoring systems and additional safeguards to prevent this from happening again.\n\nWe value your trust in our platform.\n\nWith sincere apologies,\nCTO",
    ),
]
