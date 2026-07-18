# DPDP ACT NOTICE & CONSENT COPY
**Version:** 1.0 | **Date:** July 18, 2026  
**Languages:** English (`en`), Hindi (`hi`), Hinglish (`hi-Latn`), Odia (`or`)

This document contains the user-facing text and voice scripts required for compliance with the **Digital Personal Data Protection (DPDP) Act, 2023** and its **2025/2026 Rules** implementation.

---

## 1. First-Contact Consent Notice (WhatsApp)
*   **Trigger:** Sent to patients on their very first interaction with the WhatsApp bot, appended cleanly to the greeting message.
*   **Rule:** Continued messaging constitutes consent to process data solely for booking. The link redirects to the clinic’s privacy policy.

### English (en)
> *(Your details are processed solely to manage your appointments. View Privacy Notice & rights: {{notice_link}})*

### Hindi (hi)
> *(आपकी जानकारी का उपयोग केवल आपके अपॉइंटमेंट प्रबंधन के लिए किया जाता है। गोपनीयता सूचना और अपने अधिकार देखें: {{notice_link}})*

### Hinglish (hi-Latn)
> *(Aapki details sirf aapke appointment management ke liye process ki jati hain. Privacy Notice aur apne rights dekhein: {{notice_link}})*

### Odia (or)
> *(ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ ପରିଚାଳନା ପାଇଁ ହିଁ କେବଳ ଆପଣଙ୍କ ତଥ୍ୟ ବ୍ୟବହାର କରାଯିବ। ପ୍ରାଇଭେସି ନୋଟିସ ଏବଂ ନିଜର ଅଧିକାର ଦେଖନ୍ତୁ: {{notice_link}})*

---

## 2. Recorded Voice Consent Script (Exotel / Plivo Integration)
*   **Trigger:** Played automatically at the start of any voice call answered by Vaani before routing to the agent.
*   **Variables:** `{{1}}` = Clinic Name

### English (en)
> Thank you for calling {{1}}. This call is answered by Vaani, our AI receptionist. To manage your booking, we process your phone number and conversation. For quality and security, this call may be recorded under the DPDP Act. To proceed, please stay on the line or press 1. If you do not consent, you may hang up and book via our WhatsApp assistant.

### Hindi (hi)
> {{1}} में कॉल करने के लिए धन्यवाद। इस कॉल का उत्तर हमारी AI रिसेप्शनिस्ट वाणी द्वारा दिया जा रहा है। अपॉइंटमेंट बुक करने के लिए, हम आपके फ़ोन नंबर और बातचीत को प्रोसेस करते हैं। गुणवत्ता और सुरक्षा के लिए, इस कॉल को DPDP एक्ट के तहत रिकॉर्ड किया जा सकता है। जारी रखने के लिए कृपया लाइन पर बने रहें या 1 दबाएं। यदि आप सहमत नहीं हैं, तो कॉल काटकर हमारे व्हाट्सएप असिस्टेंट द्वारा बुक कर सकते हैं।

### Hinglish (hi-Latn)
> {{1}} mein call karne ke liye dhanyawad. Is call ka answer humari AI receptionist Vaani de rahi hai. Appointment book karne ke liye, hum aapka phone number aur conversation process karte hain. Quality aur security ke liye, is call ko DPDP Act ke tehat record kiya ja sakta hai. Aage badhne ke liye kripya line par bane rahein ya 1 press karein. Agar aap agree nahi karte, toh call disconnect karke humare WhatsApp assistant se book kar sakte hain.

### Odia (or)
> {{1}} କୁ କଲ୍ କରିଥିବାରୁ ଧନ୍ୟବାଦ। ଏହି କଲ୍ ର ଉତ୍ତର ଆମର AI ରିସେପସନିଷ୍ଟ ବାଣୀ ପ୍ରଦାନ କରୁଛନ୍ତି। ଆପଣଙ୍କ ବୁକିଂ ପରିଚାଳନା ପାଇଁ ଆମେ ଆପଣଙ୍କ ଫୋନ୍ ନମ୍ବର ଏବଂ କଥାବାର୍ତ୍ତାକୁ ପ୍ରୋସେସ୍ କରିଥାଉ। ଗୁଣବତ୍ତା ଏବଂ ସୁରକ୍ଷା ପାଇଁ, DPDP ଆକ୍ଟ ଅନୁସାରେ ଏହି କଲ୍ ଟି ରେକର୍ଡ କରାଯାଇପାରେ। ଆଗକୁ ବଢିବା ପାଇଁ ଦୟାକରି ଲାଇନରେ ରୁହନ୍ତୁ କିମ୍ବା 1 ଦବାନ୍ତୁ। ଯଦି ଆପଣ ଏଥିରେ ସହମତ ନୁହଁନ୍ତି, ତେବେ କଲ୍ କାଟି ଆମର ହ୍ୱାଟ୍ସଆପ୍ ଆସିଷ୍ଟାଣ୍ଟ ଜରିଆରେ ବୁକ୍ କରିପାରିବେ।

---

## 3. Web Privacy Notice Template (Clinic Privacy Policy Link Destination)
*   **Deployment:** Hosted as a static page on the clinic's tenant subdomain (e.g. `https://{{tenant_slug}}.vaani.ai/privacy-notice`).
*   **Format:** Straightforward, high-readability layout structured for mobile screens.

```markdown
# PRIVACY NOTICE & PATIENT RIGHTS
**Last Updated:** July 2026  
**Data Fiduciary (Clinic):** {{clinic_name}} (Address: {{clinic_address}})  
**Data Processor:** Xolver Technologies Private Limited (Vaani Platform)  

Under the Digital Personal Data Protection (DPDP) Act, 2023, you have specific rights regarding the personal data we collect when you interact with our AI front-desk receptionist on WhatsApp or Voice call.

### 1. What Data We Collect
We collect and process only the minimum information necessary to schedule and manage your medical appointments:
*   **Phone Number:** Used to identify you and send booking updates.
*   **Name:** Captured to record who the appointment is for.
*   **Appointment Details:** Date, time, chosen doctor, and service type (e.g., consultation, cleaning).
*   **Conversation logs & call recordings:** Retained for booking validation and receptionist quality training.

### 2. Purpose of Processing
Your data is processed solely on the instructions of the Clinic (the Data Fiduciary) to:
1. Schedule, confirm, reschedule, or cancel your clinic visits.
2. Send transactional reminders and secure billing/payment links.
3. Respond to your questions about clinic timings, fees, and location.

*We never sell your data, use it for third-party marketing, or share it with unauthorized entities.*

### 3. Your Rights as a Data Principal
Under the DPDP Act, you possess the following rights which you can exercise at any time:
*   **Right to Access:** Request a summary of the personal data we hold about you and the processing activities.
*   **Right to Correction & Erasure:** Correct any inaccurate details, or request that we delete all your personal data (the "Right to be Forgotten") from the clinic's and processor's systems.
*   **Right to Withdraw Consent:** You can withdraw your consent for future booking reminders by replying "STOP" at any time.

### 4. How to Exercise Your Rights (Erasure / Deletion)
To delete your phone number, chat transcripts, and records from our system:
1. Send a WhatsApp message to this number with the words **"DELETE MY DATA"** or **"मेरा डेटा डिलीट करो"**.
2. Our AI will automatically verify your request and flag it to the clinic manager.
3. Your personal identifiable data (PII) will be completely purged from our active databases and backup logs within **7 calendar days**, in compliance with the DPDP SLA.

### 5. Grievance Redressal
If you have any questions, concerns, or complaints regarding how your data is handled:
*   **Clinic Data Officer:** {{grievance_officer_name}} (Email: {{grievance_officer_email}})
*   **Grievance Officer (Vaani Platform):** Subham Jena, Xolver Technologies (Email: support@vaani.ai)
```
