# SalonAI Workforce Platform: System Architecture & AI Agent Workflows

This document provides a comprehensive, in-depth blueprint of the SalonAI Workforce Platform. It details the system's end-to-end execution flow, the design of the multi-agent orchestrator, the dynamic capability-routing mechanisms, and the individual state machines governing the six specialized AI agents.

---

## 1. High-Level Project Architecture

The SalonAI Workforce Platform leverages a robust **three-tier architecture** designed for high-throughput, multi-tenant conversational operations:
1. **Presentation Tier (Frontend)**: Real-time UI that initiates chats, manages ongoing session IDs, and handles user roles (Customers, Stylists, Admins).
2. **Application Tier (FastAPI & AI Workforce Backend)**: Contains the API routing endpoints, the multi-agent orchestrator (`OrchestratorV3`), token optimizer caching, event dispatchers, semantic RAG pipelines, and the dynamic `WorkflowRegistry`.
3. **Database Tier (Supabase & SQLite)**: Exposes persistence for tenant data, branches, reviews, leads, bookings, customer profiles, staff details, chat logs, and vector embeddings for semantic search.

### System Architecture State Diagram

The diagram below maps the complete lifecycle of a request, from client invocation, orchestrator interception, intent classification, agent dispatching, and transaction handling, down to formatting and response delivery.

```mermaid
stateDiagram-v2
    [*] --> Idle : Client Ready
    
    state Presentation_Tier {
        Idle --> Router_Received : "POST /api/agent/chat\n(Message, SessionID, UserRole)"
    }
    
    state API_Router_Gateway {
        Router_Received --> Store_User_Message : "Log message to ChatLog"
        Store_User_Message --> Reset_Lead_Check : "Active Lead Reset to 'NEW'"
        Reset_Lead_Check --> Check_Timeout_Threshold : "Awaiting agent execution"
        
        state Timeout_Fallback_Fork <<choice>>
        Check_Timeout_Threshold --> Timeout_Fallback_Fork
        Timeout_Fallback_Fork --> Sync_Processing : "Under 30 Seconds"
        Timeout_Fallback_Fork --> Async_Background_Fork : "Exceeds 30 Seconds"
        
        Async_Background_Fork --> Deliver_Pending_Response : "Return 'Processing...'"
        Deliver_Pending_Response --> [*]
    }
    
    state Orchestrator_Pipeline {
        Sync_Processing --> Set_Tenant_Context : "Initialize TenantContext"
        Async_Background_Fork --> Set_Tenant_Context : "Background Thread Init"
        
        Set_Tenant_Context --> Check_Result_Cache : "Inspect ResultCache\n(Dashboard, Revenue, Forecasts)"
        
        state Cache_Match_Fork <<choice>>
        Check_Result_Cache --> Cache_Match_Fork
        Cache_Match_Fork --> Cache_Hit : "HIT"
        Cache_Match_Fork --> Permission_Check : "MISS"
        
        Cache_Hit --> Format_Cached_Output : "Bypass LLM Processing"
        
        Permission_Check --> Verify_Plan_Eligibility : "EnterprisePermissionGuard"
        
        state Permission_Fork <<choice>>
        Verify_Plan_Eligibility --> Permission_Fork
        Permission_Fork --> Access_Denied_Response : "Invalid Role or Plan Gated"
        Permission_Fork --> Intent_Resolution : "Authorized"
        
        Access_Denied_Response --> Format_System_Output : "Generate Error Message"
        
        state Intent_Classifier {
            Intent_Resolution --> Sticky_Booking_Check : "Active 'pending_booking'?"
            Sticky_Booking_Check --> Rule_Based_Classifier : "No"
            Sticky_Booking_Check --> Resolve_Agent_Target : "Yes -> Force Clara"
            
            Rule_Based_Classifier --> Validate_Role_Intents : "Keyword Matched"
            Rule_Based_Classifier --> LLM_Fallback_Classifier : "Unknown Intent"
            LLM_Fallback_Classifier --> Validate_Role_Intents : "Classify intent via LLM"
            
            Validate_Role_Intents --> Resolve_Agent_Target : "Role-Boundary Cleanse\n(Block Customer from BI/Staff)"
        }
        
        state Query_Enrichment {
            Resolve_Agent_Target --> Load_Conversation_Context : "Fetch prior turns from StateService"
            Load_Conversation_Context --> Resolve_Entities : "EntityResolverService\n(Convert relative names/dates to UUIDs)"
            Resolve_Entities --> Query_RAG_Domains : "Retrieve unified RAG contexts\n(Policy, Lead, Staff, BI, Cust)"
            Query_RAG_Domains --> Enforce_Token_Budget : "TokenOptimizer Budget Limit\n(Hard cap: 3000 tokens)"
        }
    }
    
    state Specialist_Agent_Cluster {
        Enforce_Token_Budget --> Dispatch_Agent : "Awaiting agent execution"
        
        state Group_Mode_Fork <<choice>>
        Dispatch_Agent --> Group_Mode_Fork
        Group_Mode_Fork --> Single_Agent_Execution : "use_team = False"
        Group_Mode_Fork --> Selector_Group_Chat : "use_team = True"
        
        Single_Agent_Execution --> Evaluate_Query : "Selected Agent analyzes prompt"
        Selector_Group_Chat --> Evaluate_Query : "Selector decides speaker turn"
        
        Evaluate_Query --> Decision_Loop : "LLM Execution"
        
        state Tool_Call_Required <<choice>>
        Decision_Loop --> Tool_Call_Required
        Tool_Call_Required --> Dynamic_Capability_Routing : "Yes (Tool needed)"
        Tool_Call_Required --> Agent_Final_Response : "No (Conversational)"
    }
    
    state Action_Registry_Handlers {
        Dynamic_Capability_Routing --> Retrieve_Registry : "Get WorkflowRegistry Instance"
        Retrieve_Registry --> Construct_Handler_Context : "Initialize HandlerContext\n(TenantID, Role, TraceID, Params)"
        Construct_Handler_Context --> Dict_Lookup : "Lookup (Workflow, Action)\nin registry (Zero if/else chains)"
        Dict_Lookup --> Verify_Action_Permissions : "BaseHandler.validate() & PermissionGuard"
        Verify_Action_Permissions --> Run_Business_Transaction : "Execute handler.handle()"
        
        state Database_Tier {
            Run_Business_Transaction --> Execute_DB_Operations : "Query Supabase via SQLAlchemy\n(CRUD / Transactions)"
        }
        
        Execute_DB_Operations --> Return_Raw_Result : "Success / Failure Payload"
        Return_Raw_Result --> Result_Compression : "TokenOptimizer compression\n(Cap output to 400 tokens)"
        Result_Compression --> Evaluate_Query : "Feed compressed output back to Agent"
    }
    
    state Response_Output_Pipeline {
        Agent_Final_Response --> Format_Response : "Format raw outputs"
        Format_Cached_Output --> Format_Response
        Format_System_Output --> Format_Response
        
        state JSON_Output_Fork <<choice>>
        Format_Response --> JSON_Output_Fork
        JSON_Output_Fork --> Convert_Raw_JSON : "Raw JSON / Dict returned"
        JSON_Output_Fork --> Complete_Response : "Friendly Markdown returned"
        
        Convert_Raw_JSON --> Complete_Response : "Run LLM Formatter Fallback\n(Convert data to Markdown tables)"
        
        Complete_Response --> Store_Assistant_Message : "Save response to ChatLog"
        Store_Assistant_Message --> Deliver_To_Client : "Return payload to user"
    }
    
    Deliver_To_Client --> [*] : Complete Turn
```

---

## 2. The 6 Agent Workflow State Charts

Each of the six specialist agents operates inside a customized state machine. They inherit features from Microsoft AutoGen and interact with the database via dedicated workflows in the `WorkflowRegistry`.

### 2.1 Clara — AI Receptionist Agent

Clara handles bookings, scheduling, availability queries, cancellations, and salon policies.

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> User_Query_Received : "Input processed"
    
    state Clara_Workflow {
        User_Query_Received --> Resolve_Target_Entities : "EntityResolver checks names/dates"
        Resolve_Target_Entities --> Fetch_Customer_History : "Extract Customer profile context"
        
        state Determine_Clara_Intent <<choice>>
        Fetch_Customer_History --> Determine_Clara_Intent
        
        Determine_Clara_Intent --> Process_Check_Availability : "Check slots"
        Determine_Clara_Intent --> Process_Book : "Book appointment"
        Determine_Clara_Intent --> Process_Reschedule : "Move appointment"
        Determine_Clara_Intent --> Process_Cancel : "Cancel appointment"
        Determine_Clara_Intent --> Process_FAQ : "Policy / FAQ query"
        
        state Process_Check_Availability {
            Verify_Input_Params --> Query_Availability_Service : "Check slots in database"
            
            state Slots_Available <<choice>>
            Query_Availability_Service --> Slots_Available
            Slots_Available --> Formulate_Slots_List : "Slots found"
            Slots_Available --> Suggest_Alternative_Stylists : "Stylist on leave / Fully booked"
        }
        
        state Process_Book {
            Check_Existing_Slots --> Validate_Booking_Data : "Branch, Service, Date, Time verified?"
            
            state Info_Complete <<choice>>
            Validate_Booking_Data --> Info_Complete
            Info_Complete --> Ask_Clarification : "No (Missing details)"
            Info_Complete --> Create_Booking_Record : "Yes (Details confirmed)"
            
            Create_Booking_Record --> Apply_Loyalty_Rules : "Calculate earned points"
        }
        
        state Process_Reschedule {
            Locate_Active_Appointment : "Search matching active booking"
            Locate_Active_Appointment --> Validate_New_Slot : "Check slots on new date/time"
            Validate_New_Slot --> Update_Appointment_Time : "Modify time/stylist in DB"
        }
        
        state Process_Cancel {
            Find_Appointment : "Find confirmed/pending record"
            Find_Appointment --> Cancel_Record : "Update status to 'CANCELLED'"
            Cancel_Record --> Trigger_Cancellation_Notification : "Dispatch refund / cancellation alerts"
        }
        
        state Process_FAQ {
            Query_Policy_RAG : "Vector lookup on 'policies' & 'faq'"
            Query_Policy_RAG --> Extract_SOP_Details : "Extract salon rules"
        }
    }
    
    Formulate_Slots_List --> Formulate_Response
    Suggest_Alternative_Stylists --> Formulate_Response
    Ask_Clarification --> Formulate_Response
    Apply_Loyalty_Rules --> Formulate_Response
    Update_Appointment_Time --> Formulate_Response
    Trigger_Cancellation_Notification --> Formulate_Response
    Extract_SOP_Details --> Formulate_Response
    
    Formulate_Response --> Client_Reply : "Deliver response to client"
    Client_Reply --> [*]
```

#### Detailed Operations Flow (Clara)
- **Sanitisation and Date Repair**: Resolves text expressions like "tomorrow at 5pm" or "next Tuesday" to actual date/time structures (e.g., `2026-06-16 17:00:00`) before submitting parameters.
- **Availability Enforcement**: Clara never generates arbitrary time slots. If the requested stylist is unavailable or on leave, Clara runs `list_staff` and queries alternative staff members to present options.
- **Sticky Booking Control**: If a booking process is incomplete, the system stores details in `pending_booking`. During subsequent turns, the orchestrator keeps routing queries to Clara until the transaction completes or is cancelled.

---

### 2.2 Mia — AI Lead Follow-Up Specialist

Mia manages CRM prospects, identifies lost bookings, creates nurture campaigns, and tracks sales pipelines.

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Trigger_Signal : "Cron Scheduler trigger (60 mins)\nor manual Admin chat inquiry"
    
    state Mia_Workflow {
        Trigger_Signal --> Evaluate_CRM_Action <<choice>>
        
        Evaluate_CRM_Action --> Scan_Abandoned_Bookings : "Recover lost customers"
        Evaluate_CRM_Action --> Search_Pipeline_Leads : "Inquire lead records"
        Evaluate_CRM_Action --> Create_New_Lead : "Register prospect"
        Evaluate_CRM_Action --> Advance_Lead_Pipeline : "Update CRM stage"
        
        state Scan_Abandoned_Bookings {
            Query_No_Shows : "Select cancelled/no-shows in lookback period"
            Query_No_Shows --> Filter_Rebooked_Clients : "Filter out customers who rebooked"
            Filter_Rebooked_Clients --> Compile_Abandoned_List : "Isolate lost leads"
        }
        
        state Search_Pipeline_Leads {
            Filter_Leads_DB : "Select from leads by status / branch"
            Filter_Leads_DB --> Compile_Search_Results
        }
        
        state Create_New_Lead {
            Verify_Lead_Uniqueness : "Check email/phone to prevent duplicates"
            Verify_Lead_Uniqueness --> Insert_Lead_Record : "Status set to 'NEW'"
        }
        
        state Advance_Lead_Pipeline {
            Fetch_CRM_Record : "Retrieve lead record by ID"
            Fetch_CRM_Record --> Update_CRM_Status : "Set status (NEW -> CONTACTED -> CONVERTED)"
            Update_CRM_Status --> Log_Pipeline_Notes : "Write progress timestamps"
        }
    }
    
    Compile_Abandoned_List --> Formulate_CRM_Response
    Compile_Search_Results --> Formulate_CRM_Response
    Insert_Lead_Record --> Formulate_CRM_Response
    Log_Pipeline_Notes --> Formulate_CRM_Response
    
    state Formulate_CRM_Response {
        Generate_Nurturing_Message : "Run RAG to draft warm outreach text"
        Generate_Nurturing_Message --> Schedule_Outreach : "Register notification workflow task"
    }
    
    Schedule_Outreach --> Client_CRM_Reply
    Client_CRM_Reply --> [*]
```

#### Detailed Operations Flow (Mia)
- **CRM funnel tracking**: Mia moves prospects through status stages (`NEW` $\rightarrow$ `CONTACTED` $\rightarrow$ `INTERESTED` $\rightarrow$ `CONVERTED` $\rightarrow$ `LOST`).
- **Nurture Personalisation**: Integrates with the vector databases `search_lead_memory` and `search_customer_memory`. If a customer churned after a color treatment, Mia drafts follow-ups offering discounts on touch-ups.
- **Outreach Scheduling**: Rather than sending notifications directly, Mia registers scheduling details via `crm_workflow_v2(action='send_followup')`, allowing background schedulers to send alerts via the requested communication channel.

---

### 2.3 Max — AI Upsell Specialist

Max drives add-on sales, suggests upgrades during bookings, and records acceptances.

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Booking_Flow_Intercept : "Booking query detected"
    
    state Max_Workflow {
        Booking_Flow_Intercept --> Load_Customer_Profile : "Retrieve styling history"
        Load_Customer_Profile --> Query_Service_RAG : "Fetch active promotions & styling FAQ"
        Query_Service_RAG --> Execute_Upsell_Rules : "Evaluate match combinations"
        
        state Evaluate_Upgrade_Match <<choice>>
        Execute_Upsell_Rules --> Evaluate_Upgrade_Match
        
        Evaluate_Upgrade_Match --> Generate_Add_On_Offer : "Pairing identified\n(e.g., Haircut -> Add Beard Trim)"
        Evaluate_Upgrade_Match --> Proceed_Standard_Booking : "No eligible pairing"
        
        Generate_Add_On_Offer --> Await_Customer_Response
        
        state Customer_Decision <<choice>>
        Await_Customer_Response --> Customer_Decision
        
        Customer_Decision --> Record_Acceptance : "Yes"
        Customer_Decision --> Record_Rejection : "No"
        
        state Record_Acceptance {
            Update_Appointment_Service : "Add service to appointment"
            Update_Appointment_Service --> Log_Acceptance_Metrics : "Track conversion & revenue"
        }
        
        state Record_Rejection {
            Log_Rejection_Metrics : "Update upsell analytics"
        }
    }
    
    Proceed_Standard_Booking --> Formulate_Max_Response
    Log_Acceptance_Metrics --> Formulate_Max_Response
    Log_Rejection_Metrics --> Formulate_Max_Response
    
    Formulate_Max_Response --> Send_Upsell_Reply
    Send_Upsell_Reply --> [*]
```

#### Detailed Operations Flow (Max)
- **Matching recommendations**: Max runs `recommendation_workflow_v2(action='get_recommendations')` to analyze customer appointment history. If a client books a "Balayage" every 6 weeks, Max recommends a "Gloss Treatment" upgrade.
- **Conversion Tracking**: Tracks accepted and rejected recommendations to update performance dashboards. Max works directly with the `AnalyticsService` to report monthly upsell revenue performance.

---

### 2.4 Olivia — AI Reputation Manager

Olivia monitors reviews, checks rating sentiment, drafts responses, and escalates complaints.

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Review_Activity_Request : "Query received"
    
    state Olivia_Workflow {
        Review_Activity_Request --> Load_Reviews : "Fetch reviews (filters: staff_id, rating)"
        
        state Determine_Olivia_Action <<choice>>
        Load_Reviews --> Determine_Olivia_Action
        
        Determine_Olivia_Action --> Run_Reputation_Analytics : "Reputation Scorecard"
        Determine_Olivia_Action --> Process_Critical_Reviews : "Alert on critical ratings"
        Determine_Olivia_Action --> Process_Review_Response : "Respond to feedback"
        
        state Run_Reputation_Analytics {
            Compute_Sentiment_Distribution : "Calculate rating averages"
            Compute_Sentiment_Distribution --> Compile_Scorecard_Report
        }
        
        state Process_Critical_Reviews {
            Filter_Low_Ratings : "Filter for rating <= 2 stars"
            
            state Critical_Found <<choice>>
            Filter_Low_Ratings --> Critical_Found
            
            Critical_Found --> Flag_For_Escalation : "Yes"
            Critical_Found --> Log_Normal_Review : "No"
            
            Flag_For_Escalation --> Trigger_Escalation_Workflow : "reputation_workflow_v2(action='escalate')"
        }
        
        state Process_Review_Response {
            Analyze_Review_Text : "Inspect customer comments"
            Analyze_Review_Text --> Retrieve_Brand_Policy : "RAG query for salon brand voice guidelines"
            Retrieve_Brand_Policy --> Draft_Response_Payload : "Generate draft text"
        }
    }
    
    Compile_Scorecard_Report --> Formulate_Olivia_Response
    Trigger_Escalation_Workflow --> Formulate_Olivia_Response
    Log_Normal_Review --> Formulate_Olivia_Response
    Draft_Response_Payload --> Formulate_Olivia_Response
    
    Formulate_Olivia_Response --> Deliver_Reputation_Reply
    Deliver_Reputation_Reply --> [*]
```

#### Detailed Operations Flow (Olivia)
- **Urgent Escalations**: 1-star reviews or comments with highly negative sentiment trigger immediate escalations. Olivia logs these as alerts for the management team.
- **Brand Voice Consistency**: When drafting responses via `reputation_workflow_v2(action='respond')`, Olivia retrieves context from `reputation_memory` to ensure replies are professional, empathetic, and offer appropriate resolutions.

---

### 2.5 Atlas Staff — AI Staff Assistant Agent

Atlas Staff helps salon stylists manage schedules, check customer preferences, and log leaves.

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Staff_Query_Received : "Stylist request input"
    
    state Atlas_Staff_Workflow {
        Staff_Query_Received --> Validate_Staff_Role : "Verify caller has STAFF permissions"
        
        state Authorized_Staff_Action <<choice>>
        Validate_Staff_Role --> Authorized_Staff_Action
        Authorized_Staff_Action --> Access_Denied : "No (Blocked / Demoted)"
        Authorized_Staff_Action --> Fetch_Staff_Metrics : "Yes (Proceed)"
        
        state Fetch_Staff_Metrics {
            Determine_Staff_Intent <<choice>>
            
            Determine_Staff_Intent --> View_Agenda : "Check schedules"
            Determine_Staff_Intent --> View_Client_Detail : "Client preferences"
            Determine_Staff_Intent --> View_Personal_KPIs : "Check performance"
            Determine_Staff_Intent --> Register_Leave : "Request leave"
            Determine_Staff_Intent --> Trigger_Reminders : "Customer alerts"
            
            state View_Agenda {
                Query_Appointments_Schedule : "Check stylist schedule"
                Query_Appointments_Schedule --> Format_Schedule_Table : "Format as Markdown table"
            }
            
            state View_Client_Detail {
                Search_Preferences : "Query styling_preferences & history"
                Search_Preferences --> Extract_Client_Alerts : "Highlight allergies / service notes"
            }
            
            state View_Personal_KPIs {
                Calculate_Personal_Revenues : "Fetch revenue generated"
                Calculate_Personal_Revenues --> Fetch_Stylist_Ratings : "Fetch average rating"
            }
            
            state Register_Leave {
                Validate_Leave_Dates : "Check date parameters"
                Validate_Leave_Dates --> Insert_Leave_Record : "Save leave to database"
            }
            
            state Trigger_Reminders {
                Fetch_Pending_Reminders : "Find unconfirmed bookings"
                Fetch_Pending_Reminders --> Dispatch_Reminder_Notifications : "Send SMS/Email alerts"
            }
        }
    }
    
    Access_Denied --> Formulate_Staff_Response
    Format_Schedule_Table --> Formulate_Staff_Response
    Extract_Client_Alerts --> Formulate_Staff_Response
    Fetch_Stylist_Ratings --> Formulate_Staff_Response
    Insert_Leave_Record --> Formulate_Staff_Response
    Dispatch_Reminder_Notifications --> Formulate_Staff_Response
    
    Formulate_Staff_Response --> Deliver_Staff_Reply
    Deliver_Staff_Reply --> [*]
```

#### Detailed Operations Flow (Atlas Staff)
- **Styling Preferences Lookup**: Atlas Staff searches for customer notes (e.g., "allergic to ammonia dye" or "prefers blonde highlights") so stylists can review client histories before appointments.
- **Performance Dashboards**: Stylists can check their individual utilization rates and client retention scores to track personal performance metrics.
- **Leave Request Validations**: When stylists log leaves, Atlas Staff verifies date parameters before saving the request to the database.

---

### 2.6 Atlas BI — AI Business Intelligence Analyst

Atlas BI provides business metrics, revenue forecasts, and custom SQL analytics to admins.

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Corporate_Analytics_Query : "Admin request input"
    
    state Atlas_BI_Workflow {
        Corporate_Analytics_Query --> Validate_Admin_Permissions : "Verify ADMIN / OWNER role"
        
        state Authorized_BI_Action <<choice>>
        Validate_Admin_Permissions --> Authorized_BI_Action
        Authorized_BI_Action --> Access_Denied_BI : "No (Demoted to Clara)"
        Authorized_BI_Action --> Load_Historical_BI_Context : "Yes (Proceed)"
        
        Load_Historical_BI_Context --> Fetch_RAG_Business_Snapshots : "Retrieve past 90 days of metrics"
        
        state Process_BI_Intent <<choice>>
        Fetch_RAG_Business_Snapshots --> Process_BI_Intent
        
        Process_BI_Intent --> Compile_Dashboard : "Business dashboard"
        Process_BI_Intent --> Calculate_Revenue_Breakdown : "Revenue trends"
        Process_BI_Intent --> Generate_Forecasts : "Financial forecasting"
        Process_BI_Intent --> Run_Custom_Query : "Execute custom SQL"
        Process_BI_Intent --> Process_Cohort_Reminders : "Loyalty reminders"
        
        state Compile_Dashboard {
            Aggregate_All_Metrics : "Fetch revenue, conversion, reviews, and bookings"
            Aggregate_All_Metrics --> Format_Overview_Report
        }
        
        state Calculate_Revenue_Breakdown {
            Breakdown_Revenues : "Group by branch, stylist, and service"
            Breakdown_Revenues --> Format_Financial_Table
        }
        
        state Generate_Forecasts {
            Execute_Forecast_Service : "Calculate expected next month metrics (+8% model)"
            Execute_Forecast_Service --> Format_Forecast_Report
        }
        
        state Run_Custom_Query {
            Parse_SQL_Input : "Parse target SELECT query"
            
            state SQL_Safety_Check <<choice>>
            Parse_SQL_Input --> SQL_Safety_Check
            SQL_Safety_Check --> Block_Query : "Contains WRITE actions (INSERT, UPDATE, DELETE)"
            SQL_Safety_Check --> Execute_Read_SQL : "Read-only SELECT query"
            
            Execute_Read_SQL --> Limit_SQL_Output : "Auto-apply LIMIT 50 constraint"
        }
        
        state Process_Cohort_Reminders {
            Query_Loyal_Cohorts : "Select customers with >= 2 bookings"
            Query_Loyal_Cohorts --> Dispatch_Cohort_Loyalty_Alerts : "Trigger reminders"
        }
    }
    
    Access_Denied_BI --> Formulate_BI_Response
    Format_Overview_Report --> Formulate_BI_Response
    Format_Financial_Table --> Formulate_BI_Response
    Format_Forecast_Report --> Formulate_BI_Response
    Block_Query --> Formulate_BI_Response
    Limit_SQL_Output --> Formulate_BI_Response
    Dispatch_Cohort_Loyalty_Alerts --> Formulate_BI_Response
    
    Formulate_BI_Response --> Deliver_BI_Reply
    Deliver_BI_Reply --> [*]
```

#### Detailed Operations Flow (Atlas BI)
- **RAG-based BI Context**: When asked analytical questions (e.g., "Why did revenue drop?"), Atlas BI queries `mcp_read(resource='business_context')` to analyze trends over the past 90 days rather than just returning current metrics.
- **SQL Security Guardrails**: The custom SQL execution tool parses inputs to block write operations (`INSERT`, `UPDATE`, `DELETE`, `DROP`). It also automatically appends `LIMIT 50` to queries to prevent database strain.
- **McKinsey-Style Formatting**: Synthesizes dashboard aggregates, financial trends, and forecasts into structured Markdown tables and bullet points.

---

## 3. Core Architecture Component Deep-Dive

Here is a breakdown of the key platform modules that support the workforce platform:

| Component | Responsibility | Performance Impact |
| :--- | :--- | :--- |
| **`FastAPI Gateway`** | Exposes `/agent/chat` endpoints, handles role checks, and manages timeouts by forking long-running requests to background workers. | Pre-allocates sessions in <5ms. |
| **`OrchestratorV3`** | Sets tenant context, handles caching, checks user permissions, identifies intents, and enriches prompts. | Saves LLM calls via cache hits. |
| **`ResultCache`** | Caches analytics and forecasts to reduce LLM token usage. | Returns cached dashboard data in <2ms. |
| **`StateService`** | Manages conversation histories and supports sticky routing for incomplete bookings. | Minimizes conversation memory overhead. |
| **`EntityResolver`** | Resolves names and relative date expressions to matching database UUIDs before executing agent workflows. | Prevents booking failures from ambiguous inputs. |
| **`Unified RAG`** | Gathers domain context (Policy, CRM, BI, Staff, Customer) to enrich system prompts. | Restricts searches to 2 documents (<800 chars). |
| **`Token Budgeter`** | Truncates histories to enforce a 3000-token cap on prompts. | Prevents model context overflows. |
| **`WorkflowRegistry`** | Maps actions to handlers dynamically via dictionary lookups instead of long conditional chains. | Executes lookups in <1ms. |
| **`BaseHandler`** | Subclasses run input validation, enforce action permissions, and execute database transactions. | Ensures consistent database operations. |
| **`Supabase/PostgreSQL`** | Persists salon configurations, bookings, leads, reviews, and transaction details. | Supports index-optimized queries. |
