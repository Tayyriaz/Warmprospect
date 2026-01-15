# Multi-Level CTA Guide

## Core Concept

**You store CTAs as a tree (like folders). Backend only decides where to enter the tree. Each time a user clicks a CTA, the frontend sends the action to the backend, and the backend responds with the next level of CTAs.**

---

## How It Works

### Backend Responsibility
- Detects user intent from messages
- Returns `ctas` array with CTA objects for the current level (not nested children)
- When frontend sends a CTA action, backend looks up that CTA's children and returns them
- Each response contains only the CTAs for the current level

### Frontend Responsibility
- Receives message and `ctas` array from backend
- Displays the message and renders CTAs as buttons
- When user clicks a CTA:
  - If `action` is `show_children`: sends CTA ID to backend to get children
  - If `action` is `redirect`: navigates to URL
  - If `action` is `send`: sends message back to backend
- Each click goes back to backend to get next level

### CTA Node Structure

Each CTA object has:
- `id` (string, unique identifier)
- `label` (string, text to display)
- `action` (string: `show_children`, `redirect`, or `send`)
- `url` (string, required if action is `redirect`)
- `message` (string, required if action is `send`)

Note: `children` is NOT sent to frontend - backend looks it up when needed.

---

## Complete Example: Business Service Inquiry (GoAccel - Home Services Growth Platform)

This example shows how a business (GoAccel) uses multi-level CTAs to guide potential customers through their services, from initial engagement to booking appointments and capturing leads.

### The Complete CTA Tree (Stored in Database/Config)

```json
{
  "learn_services": {
    "id": "learn_services",
    "label": "Learn About Services",
    "action": "show_children",
    "children": ["digital_agency", "website_design", "business_growth", "crm_platform"]
  },
  "digital_agency": {
    "id": "digital_agency",
    "label": "Digital Agency Solutions",
    "action": "show_children",
    "children": ["agency_info", "agency_pricing", "agency_book"]
  },
  "agency_info": {
    "id": "agency_info",
    "label": "What's Included",
    "action": "send",
    "message": "Tell me about your digital agency solutions and what services are included."
  },
  "agency_pricing": {
    "id": "agency_pricing",
    "label": "Pricing & Packages",
    "action": "send",
    "message": "What are your digital agency pricing options and packages?"
  },
  "agency_book": {
    "id": "agency_book",
    "label": "Book Consultation",
    "action": "send",
    "message": "I'd like to book a consultation to discuss digital agency services."
  },
  "website_design": {
    "id": "website_design",
    "label": "Website Design Services",
    "action": "show_children",
    "children": ["design_portfolio", "design_process", "design_quote"]
  },
  "design_portfolio": {
    "id": "design_portfolio",
    "label": "View Portfolio",
    "action": "redirect",
    "url": "https://goaccel.com/portfolio"
  },
  "design_process": {
    "id": "design_process",
    "label": "Our Process",
    "action": "send",
    "message": "Can you walk me through your website design process?"
  },
  "design_quote": {
    "id": "design_quote",
    "label": "Get a Quote",
    "action": "send",
    "message": "I'd like to get a quote for website design services."
  },
  "business_growth": {
    "id": "business_growth",
    "label": "Business Growth Services",
    "action": "show_children",
    "children": ["growth_strategy", "growth_visibility", "growth_book"]
  },
  "growth_strategy": {
    "id": "growth_strategy",
    "label": "Growth Strategy",
    "action": "send",
    "message": "Tell me about your business growth strategy services."
  },
  "growth_visibility": {
    "id": "growth_visibility",
    "label": "Free Visibility Scan",
    "action": "send",
    "message": "I'd like to get a free visibility scan for my business."
  },
  "growth_book": {
    "id": "growth_book",
    "label": "Book Growth Call",
    "action": "send",
    "message": "I want to book a 15-minute growth call to learn more."
  },
  "crm_platform": {
    "id": "crm_platform",
    "label": "CRM Software Platform",
    "action": "show_children",
    "children": ["crm_features", "crm_demo", "crm_pricing"]
  },
  "crm_features": {
    "id": "crm_features",
    "label": "Features & Benefits",
    "action": "send",
    "message": "What features does your CRM platform offer?"
  },
  "crm_demo": {
    "id": "crm_demo",
    "label": "Request Demo",
    "action": "send",
    "message": "I'd like to see a demo of your CRM platform."
  },
  "crm_pricing": {
    "id": "crm_pricing",
    "label": "Pricing Plans",
    "action": "redirect",
    "url": "https://goaccel.com/crm/pricing"
  },
  "book_appointment": {
    "id": "book_appointment",
    "label": "Book an Appointment",
    "action": "show_children",
    "children": ["appt_growth_call", "appt_consultation", "appt_demo"]
  },
  "appt_growth_call": {
    "id": "appt_growth_call",
    "label": "15-Min Growth Call",
    "action": "redirect",
    "url": "https://calendly.com/goaccel/growth-call"
  },
  "appt_consultation": {
    "id": "appt_consultation",
    "label": "Full Consultation",
    "action": "redirect",
    "url": "https://calendly.com/goaccel/consultation"
  },
  "appt_demo": {
    "id": "appt_demo",
    "label": "Product Demo",
    "action": "redirect",
    "url": "https://calendly.com/goaccel/demo"
  },
  "speak_sales": {
    "id": "speak_sales",
    "label": "Speak to Sales",
    "action": "send",
    "message": "I'd like to speak with a sales representative."
  }
}
```

### Scenario 1: User Wants to Learn About Services

#### Step 1: User Message
```
User: "I'm looking for a laptop"
```

#### Step 2: Backend Response (Entry Point)
Backend detects intent and returns entry point CTA:

```json
{
  "response": "Great! I can help you find the perfect laptop. What type are you interested in?",
  "ctas": [
    {
      "id": "laptops",
      "label": "Laptops",
      "action": "show_children"
    }
  ]
}
```

#### Step 3: Frontend Displays
Frontend shows:
- **Message**: "We offer a range of services to help home services businesses grow. What interests you most?"
- **CTA Button**: `[ Learn About Services ]`

#### Step 4: User Clicks "Learn About Services"
Frontend sends CTA action to backend:

```javascript
// Frontend sends
POST /api/chat/cta
{
  "business_id": "goaccel",
  "session_id": "user-123",
  "cta_id": "learn_services"
}
```

#### Step 5: Backend Response (Children)
Backend looks up `learn_services` node, finds its children, and returns them:

```json
{
  "response": "Here are our main service areas:",
  "ctas": [
    {
      "id": "digital_agency",
      "label": "Digital Agency Solutions",
      "action": "show_children"
    },
    {
      "id": "website_design",
      "label": "Website Design Services",
      "action": "show_children"
    },
    {
      "id": "business_growth",
      "label": "Business Growth Services",
      "action": "show_children"
    },
    {
      "id": "crm_platform",
      "label": "CRM Software Platform",
      "action": "show_children"
    }
  ]
}
```

#### Step 6: Frontend Displays
Frontend shows:
- **Message**: "Here are our main service areas:"
- **CTA Buttons**: 
  ```
  [ Digital Agency Solutions ]  [ Website Design Services ]  [ Business Growth Services ]  [ CRM Software Platform ]
  ```

#### Step 7: User Clicks "Business Growth Services"
Frontend sends:

```javascript
POST /api/chat/cta
{
  "business_id": "goaccel",
  "session_id": "user-123",
  "cta_id": "business_growth"
}
```

#### Step 8: Backend Response (Next Level)
Backend returns children of `business_growth`:

```json
{
  "response": "Our business growth services help you scale predictably. What would you like to know?",
  "ctas": [
    {
      "id": "growth_strategy",
      "label": "Growth Strategy",
      "action": "send",
      "message": "Tell me about your business growth strategy services."
    },
    {
      "id": "growth_visibility",
      "label": "Free Visibility Scan",
      "action": "send",
      "message": "I'd like to get a free visibility scan for my business."
    },
    {
      "id": "growth_book",
      "label": "Book Growth Call",
      "action": "send",
      "message": "I want to book a 15-minute growth call to learn more."
    }
  ]
}
```

#### Step 9: Frontend Displays
Frontend shows:
- **Message**: "Our business growth services help you scale predictably. What would you like to know?"
- **CTA Buttons**: 
  ```
  [ Growth Strategy ]  [ Free Visibility Scan ]  [ Book Growth Call ]
  ```

#### Step 10: User Clicks "Free Visibility Scan"
Frontend sends message to backend:

```javascript
POST /api/chat
{
  "business_id": "goaccel",
  "session_id": "user-123",
  "message": "I'd like to get a free visibility scan for my business."
}
```

Backend processes the message, may collect PII (name, email, phone) through conversation, and responds with information about the visibility scan. Flow continues in conversation.

---

### Scenario 2: User Wants to Book an Appointment

#### Step 1: User Message
```
User: "I'd like to schedule something"
```

#### Step 2: Backend Response
Backend detects appointment intent and returns entry point:

```json
{
  "response": "Great! I can help you schedule a call. What type of appointment would work best?",
  "ctas": [
    {
      "id": "book_appointment",
      "label": "Book an Appointment",
      "action": "show_children"
    }
  ]
}
```

#### Step 3: User Clicks "Book an Appointment"
Frontend sends `cta_id: "book_appointment"` to backend.

#### Step 4: Backend Response
```json
{
  "response": "Here are our available appointment types:",
  "ctas": [
    {
      "id": "appt_growth_call",
      "label": "15-Min Growth Call",
      "action": "redirect",
      "url": "https://calendly.com/goaccel/growth-call"
    },
    {
      "id": "appt_consultation",
      "label": "Full Consultation",
      "action": "redirect",
      "url": "https://calendly.com/goaccel/consultation"
    },
    {
      "id": "appt_demo",
      "label": "Product Demo",
      "action": "redirect",
      "url": "https://calendly.com/goaccel/demo"
    }
  ]
}
```

#### Step 5: User Clicks "15-Min Growth Call"
Frontend executes redirect action:

```javascript
window.location.href = "https://calendly.com/goaccel/growth-call";
```

User is redirected to the booking page. Flow complete.

---

### Scenario 3: User Explores Website Design Services

#### Step 1: User Message
```
User: "Tell me about website design"
```

#### Step 2: Backend Response
```json
{
  "response": "Our website design services help home services businesses create professional, conversion-focused websites.",
  "ctas": [
    {
      "id": "website_design",
      "label": "Website Design Services",
      "action": "show_children"
    }
  ]
}
```

#### Step 3: User Clicks "Website Design Services"
Frontend sends `cta_id: "website_design"` to backend.

#### Step 4: Backend Response
```json
{
  "response": "Here's what you can explore about our website design services:",
  "ctas": [
    {
      "id": "design_portfolio",
      "label": "View Portfolio",
      "action": "redirect",
      "url": "https://goaccel.com/portfolio"
    },
    {
      "id": "design_process",
      "label": "Our Process",
      "action": "send",
      "message": "Can you walk me through your website design process?"
    },
    {
      "id": "design_quote",
      "label": "Get a Quote",
      "action": "send",
      "message": "I'd like to get a quote for website design services."
    }
  ]
}
```

#### Step 5: User Clicks "Get a Quote"
Frontend sends message to backend:

```javascript
POST /api/chat
{
  "business_id": "goaccel",
  "session_id": "user-123",
  "message": "I'd like to get a quote for website design services."
}
```

Backend processes the request, may collect business information (company name, current website, budget range), and responds with next steps. The chatbot may use CRM tools to create a contact and deal in the system.

---

## Frontend Implementation Example

```javascript
// Handle backend response
function handleBackendResponse(response) {
  // Display the text response
  displayMessage(response.response, 'bot');
  
  // Render CTAs from backend (only current level, no nested children)
  if (response.ctas && response.ctas.length > 0) {
    renderCTAs(response.ctas);
  } else {
    // No CTAs, clear the container
    renderCTAs([]);
  }
}

// Render CTAs from array of CTA objects
function renderCTAs(ctaObjects) {
  const ctaContainer = document.getElementById('cta-container');
  ctaContainer.innerHTML = '';
  
  if (!ctaObjects || ctaObjects.length === 0) {
    return;
  }
  
  ctaObjects.forEach(cta => {
    const button = document.createElement('button');
    button.textContent = cta.label;
    button.className = 'cta-button';
    button.onclick = () => handleCTAClick(cta);
    ctaContainer.appendChild(button);
  });
}

// Handle CTA button click
function handleCTAClick(cta) {
  switch (cta.action) {
    case 'show_children':
      // Send CTA ID to backend to get children
      fetch('/api/chat/cta', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cta_id: cta.id })
      })
        .then(res => res.json())
        .then(data => handleBackendResponse(data))
        .catch(err => console.error('Error:', err));
      break;
      
    case 'redirect':
      if (cta.url) {
        window.location.href = cta.url;
      } else {
        console.error(`CTA ${cta.id} has redirect action but no URL`);
      }
      break;
      
    case 'send':
      if (cta.message) {
        sendMessage(cta.message);
      } else {
        console.error(`CTA ${cta.id} has send action but no message`);
      }
      break;
      
    default:
      console.error(`Unknown action type: ${cta.action}`);
  }
}

// Send message function (integrates with chat)
function sendMessage(message) {
  // Add user message to chat
  displayMessage(message, 'user');
  
  // Send to backend
  fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  })
    .then(res => res.json())
    .then(data => handleBackendResponse(data))
    .catch(err => console.error('Error:', err));
}
```

---

## Backend Implementation Example

```python
# CTA tree stored in database or config (per business)
# This would be stored in the business_config table or business_configs.json
CTA_TREE = {
    "learn_services": {
        "id": "learn_services",
        "label": "Learn About Services",
        "action": "show_children",
        "children": ["digital_agency", "website_design", "business_growth", "crm_platform"]
    },
    "business_growth": {
        "id": "business_growth",
        "label": "Business Growth Services",
        "action": "show_children",
        "children": ["growth_strategy", "growth_visibility", "growth_book"]
    },
    "growth_strategy": {
        "id": "growth_strategy",
        "label": "Growth Strategy",
        "action": "send",
        "message": "Tell me about your business growth strategy services."
    },
    "growth_visibility": {
        "id": "growth_visibility",
        "label": "Free Visibility Scan",
        "action": "send",
        "message": "I'd like to get a free visibility scan for my business."
    },
    "growth_book": {
        "id": "growth_book",
        "label": "Book Growth Call",
        "action": "send",
        "message": "I want to book a 15-minute growth call to learn more."
    },
    "book_appointment": {
        "id": "book_appointment",
        "label": "Book an Appointment",
        "action": "show_children",
        "children": ["appt_growth_call", "appt_consultation", "appt_demo"]
    },
    "appt_growth_call": {
        "id": "appt_growth_call",
        "label": "15-Min Growth Call",
        "action": "redirect",
        "url": "https://calendly.com/goaccel/growth-call"
    },
    # ... more nodes
}

def get_cta_children(cta_id: str) -> list:
    """
    Get children CTAs for a given CTA ID.
    Returns list of CTA objects (without nested children).
    """
    cta = CTA_TREE.get(cta_id)
    if not cta:
        return []
    
    if cta.get("action") != "show_children" or not cta.get("children"):
        return []
    
    # Return children as CTA objects (without their children)
    children_ctas = []
    for child_id in cta["children"]:
        child_cta = CTA_TREE.get(child_id)
        if child_cta:
            # Return CTA without children array (frontend doesn't need it)
            cta_obj = {
                "id": child_cta["id"],
                "label": child_cta["label"],
                "action": child_cta["action"]
            }
            if child_cta.get("url"):
                cta_obj["url"] = child_cta["url"]
            if child_cta.get("message"):
                cta_obj["message"] = child_cta["message"]
            children_ctas.append(cta_obj)
    
    return children_ctas

def process_user_message(message: str) -> dict:
    """
    Process user message and return response with entry point CTA.
    """
    # Detect intent (simplified example)
    intent = detect_intent(message)
    
    response_text = ""
    entry_point_id = None
    
    if intent == "service_inquiry":
        if any(word in message.lower() for word in ["service", "offer", "provide", "do"]):
            response_text = "We offer a range of services to help home services businesses grow. What interests you most?"
            entry_point_id = "learn_services"
        elif "website" in message.lower() or "design" in message.lower():
            response_text = "Our website design services help home services businesses create professional, conversion-focused websites."
            entry_point_id = "website_design"
        elif any(word in message.lower() for word in ["growth", "scale", "expand"]):
            response_text = "Our business growth services help you scale predictably. What would you like to know?"
            entry_point_id = "business_growth"
        elif "crm" in message.lower() or "software" in message.lower():
            response_text = "Our CRM platform helps you manage customer relationships and grow your business."
            entry_point_id = "crm_platform"
        else:
            response_text = "We offer a range of services to help home services businesses grow. What interests you most?"
            entry_point_id = "learn_services"
    elif intent == "appointment_inquiry":
        response_text = "Great! I can help you schedule a call. What type of appointment would work best?"
        entry_point_id = "book_appointment"
    elif intent == "sales_inquiry":
        response_text = "I'd be happy to connect you with our sales team. Let me know what you're interested in."
        entry_point_id = "speak_sales"
    else:
        response_text = "How can I help you today?"
        entry_point_id = "learn_services"
    
    # Get entry point CTA (without children)
    entry_cta = CTA_TREE.get(entry_point_id) if entry_point_id else None
    cta_obj = None
    if entry_cta:
        cta_obj = {
            "id": entry_cta["id"],
            "label": entry_cta["label"],
            "action": entry_cta["action"]
        }
        # Don't include children - frontend will request them when clicked
    
    return {
        "response": response_text,
        "ctas": [cta_obj] if cta_obj else []
    }

def handle_cta_click(cta_id: str) -> dict:
    """
    Handle CTA click - return children CTAs for the clicked CTA.
    """
    children = get_cta_children(cta_id)
    
    # Generate appropriate response message
    cta = CTA_TREE.get(cta_id)
    response_text = f"Here are your options for {cta.get('label', 'this category')}:" if cta else "Here are your options:"
    
    return {
        "response": response_text,
        "ctas": children
    }

def detect_intent(message: str) -> str:
    """
    Simple intent detection (in production, use Gemini or NLP).
    In WarmProspect, this could be handled by the Gemini model itself.
    """
    message_lower = message.lower()
    
    if any(word in message_lower for word in ["service", "offer", "provide", "what do you", "tell me about"]):
        return "service_inquiry"
    elif any(word in message_lower for word in ["appointment", "schedule", "book", "call", "meeting", "calendar"]):
        return "appointment_inquiry"
    elif any(word in message_lower for word in ["sales", "speak to", "talk to", "contact", "representative"]):
        return "sales_inquiry"
    else:
        return "general_inquiry"
```

---

## API Endpoints

### POST /chat
Process user message and return response with entry point CTAs.

**Request:**
```json
{
  "business_id": "goaccel",
  "session_id": "user-123",
  "message": "What services do you offer?"
}
```

**Response:**
```json
{
  "response": "We offer a range of services to help home services businesses grow. What interests you most?",
  "ctas": [
    {
      "id": "learn_services",
      "label": "Learn About Services",
      "action": "show_children"
    }
  ]
}
```

### POST /chat/cta
Handle CTA click and return children CTAs.

**Request:**
```json
{
  "business_id": "goaccel",
  "session_id": "user-123",
  "cta_id": "learn_services"
}
```

**Response:**
```json
{
  "response": "Here are our main service areas:",
  "ctas": [
    {
      "id": "digital_agency",
      "label": "Digital Agency Solutions",
      "action": "show_children"
    },
    {
      "id": "website_design",
      "label": "Website Design Services",
      "action": "show_children"
    },
    {
      "id": "business_growth",
      "label": "Business Growth Services",
      "action": "show_children"
    },
    {
      "id": "crm_platform",
      "label": "CRM Software Platform",
      "action": "show_children"
    }
  ]
}
```

---

## Key Points

1. **Backend sends one level at a time**: Each response contains only CTAs for the current level, not nested children
2. **Frontend requests next level**: When user clicks a CTA with `show_children`, frontend sends CTA ID to backend
3. **Backend looks up children**: Backend finds the clicked CTA's children and returns them
4. **No pre-loading**: Children are not sent until user clicks
5. **Tree is user-defined**: All CTA structure comes from configuration/database
6. **No hardcoded logic**: Everything is data-driven
7. **Flexible depth**: Up to 4 levels, but structure is natural
8. **Stateful conversation**: Each click goes back to backend to get next level
