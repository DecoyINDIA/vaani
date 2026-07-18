# WHATSAPP TEMPLATE PACK FOR APPROVAL
**Version:** 1.0 | **Date:** July 18, 2026  
**Languages:** English (`en`), Hindi (`hi`), Hinglish (`hi-Latn`), Odia (`or`)  
**Note:** Placeholders are represented by `{{1}}`, `{{2}}`, etc., as per Meta Cloud API standards. All templates are of category **UTILITY** unless stated otherwise.

---

## 1. T_MISSED_CALL_BRIDGE (Missed Call Follow-Up)
*   **Purpose:** Sent to a caller after they make a missed call or when the line was busy.
*   **Variables:** `{{1}}` = Clinic Name

### English (en)
> Hello! 🙏 You recently called {{1}}. Our lines were busy. I am Vaani, the clinic's AI assistant. Would you like to check available slots and book an appointment?
> `[Button 1: Show Slots]` `[Button 2: No, Thanks]`

### Hindi (hi)
> नमस्ते! 🙏 आपने अभी {{1}} को कॉल किया था। उस समय व्यस्त होने के कारण कॉल नहीं उठ पाया। मैं वाणी हूँ — क्लिनिक की AI सहायक। क्या आप उपलब्ध समय (slots) देखना और अपॉइंटमेंट बुक करना चाहेंगे?
> `[Button 1: स्लॉट दिखाएं]` `[Button 2: जी नहीं, धन्यवाद]`

### Hinglish (hi-Latn)
> Namaste! 🙏 Aapne abhi {{1}} ko call kiya tha. Line busy hone ke karan call nahi uth paya. Main Vaani hoon — clinic ki AI assistant. Kya aap available slots dekhna aur appointment book karna chahenge?
> `[Button 1: Slots Dikhayein]` `[Button 2: Ji Nahi, Thanks]`

### Odia (or)
> ନମସ୍କାର! 🙏 ଆପଣ ଏବେ {{1}} କୁ କଲ୍ କରିଥିଲେ। ସେହି ସମୟରେ ବ୍ୟସ୍ତ ଥିବା ହେତୁ କଲ୍ ଉଠିପାରିଲା ନାହିଁ। ମୁଁ ବାଣୀ — କ୍ଲିନିକର AI ସହାୟିକା। ଆପଣ ଉପଲବ୍ଧ ସମୟ (slots) ଦେଖି ଅପଏଣ୍ଟମେଣ୍ଟ ବୁକ୍ କରିବାକୁ ଚାହାନ୍ତି କି?
> `[Button 1: ସ୍ଲଟ୍ ଦେଖାନ୍ତୁ]` `[Button 2: ନାହିଁ, ଧନ୍ୟବାଦ]`

---

## 2. T_BOOKING_CONFIRMATION (Proactive Booking Confirmation)
*   **Purpose:** Sent when an appointment is booked via voice line or manual dashboard.
*   **Variables:** `{{1}}` = Patient Name, `{{2}}` = Doctor/Practitioner Name, `{{3}}` = Weekday & Date, `{{4}}` = Time, `{{5}}` = Location/Landmark
*   **Header:** Utility Alert (Optional)

### English (en)
> Hello {{1}}! Your appointment with Dr. {{2}} has been confirmed for {{3}} at {{4}}. 
> Location: {{5}}
> To modify or cancel this booking, please reply to this message.
> `[Button 1: View Location Pin]`

### Hindi (hi)
> नमस्ते {{1}}! Dr. {{2}} के साथ आपका अपॉइंटमेंट confirm हो गया है।
> दिन और तारीख: {{3}}
> समय: {{4}}
> पता: {{5}}
> अपॉइंटमेंट बदलने या कैंसिल करने के लिए कृपया यहीं मैसेज करें।
> `[Button 1: लोकेशन पिन देखें]`

### Hinglish (hi-Latn)
> Namaste {{1}}! Dr. {{2}} ke sath aapka appointment confirm ho gaya hai.
> Din aur Tareekh: {{3}}
> Samay: {{4}}
> Pata: {{5}}
> Appointment badalne ya cancel karne ke liye kripya yahin message karein.
> `[Button 1: Location Pin Dekhein]`

### Odia (or)
> ନମସ୍କାର {{1}}! ଡକ୍ଟର {{2}} ଙ୍କ ସହ ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ confirm ହୋଇଯାଇଛି।
> ଦିନ ଓ ତାରିଖ: {{3}}
> ସମୟ: {{4}}
> ଠିକଣା: {{5}}
> ଅପଏଣ୍ଟମେଣ୍ଟ ବଦଳାଇବା କିମ୍ବା ବାତିଲ୍ କରିବା ପାଇଁ ଦୟାକରି ଏଠାରେ ମେସେଜ କରନ୍ତୁ।
> `[Button 1: ଲୋକେସନ ପିନ୍ ଦେଖନ୍ତୁ]`

---

## 3. T_REMINDER_24H (24-Hour Pre-Appointment Reminder)
*   **Purpose:** Sent 24 hours before the appointment to prevent no-shows.
*   **Variables:** `{{1}}` = Patient Name, `{{2}}` = Doctor Name, `{{3}}` = Weekday & Date, `{{4}}` = Time
*   *Note: Opt-out notice included.*

### English (en)
> Hello {{1}}, this is an AI reminder that you have an appointment with Dr. {{2}} tomorrow, {{3}} at {{4}}. Please confirm your attendance:
> (Reply 'STOP' to opt out of reminders)
> `[Button 1: ✅ Yes, I will come]` `[Button 2: 🔄 Reschedule]` `[Button 3: ❌ Cancel]`

### Hindi (hi)
> नमस्ते {{1}}, यह AI अनुस्मारक (reminder) है कि कल {{3}} को {{4}} बजे Dr. {{2}} के साथ आपका अपॉइंटमेंट है। क्या आप आ रहे हैं?
> (रिमाइंडर बंद करने के लिए 'STOP' लिखें)
> `[Button 1: ✅ जी हाँ, आऊंगा]` `[Button 2: 🔄 समय बदलें]` `[Button 3: ❌ कैंसिल करें]`

### Hinglish (hi-Latn)
> Namaste {{1}}, yeh AI reminder hai ki kal {{3}} ko {{4}} baje Dr. {{2}} ke sath aapka appointment hai. Kya aap aa rahe hain?
> (Reminder band karne ke liye 'STOP' likhein)
> `[Button 1: ✅ Haan, Aaunga]` `[Button 2: 🔄 Time Badlein]` `[Button 3: ❌ Cancel Karein]`

### Odia (or)
> ନମସ୍କାର {{1}}, ଏହା ଏକ AI ରିମାଇଣ୍ଡର ଯେ ଆସନ୍ତାକାଲି {{3}} ତାରିଖ {{4}} ସମୟରେ ଡକ୍ଟର {{2}} ଙ୍କ ସହ ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ ଅଛି। ଆପଣ ଆସୁଛନ୍ତି କି?
> (ରିମାଇଣ୍ଡର ବନ୍ଦ କରିବା ପାଇଁ 'STOP' ଲେଖନ୍ତୁ)
> `[Button 1: ✅ ହଁ, ମୁଁ ଆସିବି]` `[Button 2: 🔄 ସମୟ ବଦଳାନ୍ତୁ]` `[Button 3: ❌ ବାତିଲ୍ କରନ୍ତୁ]`

---

## 4. T_REMINDER_2H (2-Hour Pre-Appointment Reminder)
*   **Purpose:** Sent 2 hours before the appointment with a direct location link.
*   **Variables:** `{{1}}` = Patient Name, `{{2}}` = Time, `{{3}}` = Clinic Landmark

### English (en)
> Hello {{1}}! Quick reminder: your appointment is in 2 hours at {{2}}.
> Landmark: {{3}}
> You can tap the button below for the exact Google Map location pin.
> `[Button 1: Get Directions Pin]`

### Hindi (hi)
> नमस्ते {{1}}! ध्यान दिला दें: आपका अपॉइंटमेंट आज ठीक {{2}} बजे है।
> लैंडमार्क: {{3}}
> सटीक लोकेशन मार्ग के लिए नीचे दिए गए बटन पर टैप करें।
> `[Button 1: दिशा-निर्देश पिन]`

### Hinglish (hi-Latn)
> Namaste {{1}}! Dhyan dila dein: aapka appointment aaj theek {{2}} baje hai.
> Landmark: {{3}}
> Exact location ke liye neeche diye button par tap karein.
> `[Button 1: Directions Pin]`

### Odia (or)
> ନମସ୍କାର {{1}}! ମନେ ପକାଇ ଦେଉଛୁ: ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ ଆଜି ଠିକ୍ {{2}} ସମୟରେ ଅଛି।
> ଲ୍ୟାଣ୍ଡମାର୍କ: {{3}}
> ସଠିକ୍ ଲୋକେସନ ଜାଣିବା ପାଇଁ ତଳେ ଦିଆଯାଇଥିବା ବଟନ୍ ଉପରେ ଟ୍ୟାପ୍ କରନ୍ତୁ।
> `[Button 1: ମାର୍ଗଦର୍ଶନ ପିନ୍]`

---

## 5. T_PAYMENT_LINK (Razorpay Payment Nudge)
*   **Purpose:** Requesting payment/deposit for the appointment.
*   **Variables:** `{{1}}` = Patient Name, `{{2}}` = Amount, `{{3}}` = Purpose/Service, `{{4}}` = Payment URL
*   *Note: Opt-out notice included.*

### English (en)
> Hello {{1}}. To secure your booking, please complete the payment of {{2}} for {{3}} using this secure UPI link: {{4}}
> A receipt will be sent here upon completion.
> (Reply 'STOP' to opt out of reminders)
> `[Button 1: Pay Now]`

### Hindi (hi)
> नमस्ते {{1}}। अपने अपॉइंटमेंट को सुरक्षित करने के लिए, कृपया {{3}} की फ़ीस {{2}} इस सुरक्षित UPI लिंक के जरिए जमा करें: {{4}}
> भुगतान पूरा होने पर रसीद यहीं भेज दी जाएगी।
> (रिमाइंडर बंद करने के लिए 'STOP' लिखें)
> `[Button 1: अभी भुगतान करें]`

### Hinglish (hi-Latn)
> Namaste {{1}}. Apne appointment ko secure karne ke liye, kripya {{3}} ki fees {{2}} is secure UPI link ke jariye pay karein: {{4}}
> Payment hone par receipt yahin mil jayegi.
> (Reminder band karne ke liye 'STOP' likhein)
> `[Button 1: Abhi Pay Karein]`

### Odia (or)
> ନମସ୍କାର {{1}}। ଆପଣଙ୍କ ବୁକିଂ ସୁରକ୍ଷିତ କରିବା ପାଇଁ, ଦୟାକରି {{3}} ବାବଦକୁ {{2}} ଟଙ୍କା ଏହି ସୁରକ୍ଷିତ UPI ଲିଙ୍କ୍ ଜରିଆରେ ପ୍ରଦାନ କରନ୍ତୁ: {{4}}
> ପେମେଣ୍ଟ ସରିଲେ ରସିଦ୍ ଏଠାରେ ମିଳିଯିବ।
> (ରିମାଇଣ୍ଡର ବନ୍ଦ କରିବା ପାଇଁ 'STOP' ଲେଖନ୍ତୁ)
> `[Button 1: ଏବେ ପେମେଣ୍ଟ କରନ୍ତୁ]`

---

## 6. T_STAFF_ALERT (Emergency Handoff Alert to Staff/Owner)
*   **Purpose:** Notification sent to the clinic receptionist or owner when a patient needs human help.
*   **Variables:** `{{1}}` = Patient Name, `{{2}}` = Patient Phone, `{{3}}` = Reason/Intent (e.g., Medical Question/Abuse/Low Confidence), `{{4}}` = Webhook/Dashboard Thread Link

### English (en)
> 🚨 Handoff Alert: Patient {{1}} ({{2}}) requires staff assistance.
> Reason: {{3}}
> Tap the button below to take over the conversation instantly.
> `[Button 1: Open Dashboard]`

### Hindi (hi)
> 🚨 टीम अलर्ट: मरीज {{1}} ({{2}}) को स्टाफ की सहायता की आवश्यकता है।
> कारण: {{3}}
> बातचीत संभालने के लिए नीचे दिए गए बटन पर क्लिक करें।
> `[Button 1: डैशबोर्ड खोलें]`

### Hinglish (hi-Latn)
> 🚨 Team Alert: Patient {{1}} ({{2}}) ko staff assistance ki jarurat hai.
> Reason: {{3}}
> Chat ko sambhalne ke liye neeche button par tap karein.
> `[Button 1: Open Dashboard]`

### Odia (or)
> 🚨 ଷ୍ଟାଫ୍ ଆଲର୍ଟ: ରୋଗୀ {{1}} ({{2}}) କୁ ଷ୍ଟାଫ୍ ସହାୟତାର ଆବଶ୍ୟକତା ଅଛି।
> କାରଣ: {{3}}
> ଏହି ଚାଟ୍ ହାତକୁ ନେବା ପାଇଁ ତଳ ବଟନ୍ ଉପରେ କ୍ଲିକ୍ କରନ୍ତୁ।
> `[Button 1: ଡ୍ୟାସବୋର୍ଡ ଖୋଲନ୍ତୁ]`

---

## 7. T_WEEKLY_SUMMARY (Weekly ROI Summary to Owner)
*   **Purpose:** Weekly automated message reporting performance and revenue recovered to the owner.
*   **Variables:** `{{1}}` = Owner/Clinic Name, `{{2}}` = Date Range, `{{3}}` = Total Conversations, `{{4}}` = Confirmed Bookings, `{{5}}` = Recovered Bookings (after-hours/missed), `{{6}}` = Estimated Recovered Value

### English (en)
> Hello {{1}}! Here is your Vaani ROI Summary for {{2}}:
> 📊 Calls & Chats Handled: {{3}}
> 📅 Appointments Booked: {{4}}
> 🔄 Recovered Bookings: {{5}} (busy lines/after-hours)
> 💰 Est. Recovered Revenue: {{6}}
> Thank you for choosing Vaani as your AI receptionist!
> `[Button 1: Open Full Analytics]`

### Hindi (hi)
> नमस्ते {{1}}! {{2}} के लिए आपका वाणी (Vaani) ROI Summary:
> 📊 संभाली गई बातचीत: {{3}}
> 📅 बुक किए गए अपॉइंटमेंट: {{4}}
> 🔄 वापस पाए गए अपॉइंटमेंट: {{5}} (व्यस्त लाइन/ड्यूटी के बाद)
> 💰 अनुमानित बची हुई कमाई: {{6}}
> वाणी को अपना AI रिसेप्शनिस्ट चुनने के लिए धन्यवाद!
> `[Button 1: पूरा विश्लेषण देखें]`

### Hinglish (hi-Latn)
> Namaste {{1}}! {{2}} ke liye aapka Vaani ROI Summary:
> 📊 Handled Calls & Chats: {{3}}
> 📅 Booked Appointments: {{4}}
> 🔄 Recovered Bookings: {{5}} (busy line/after-hours)
> 💰 Est. Recovered Revenue: {{6}}
> Vaani ko apna AI receptionist chunne ke liye thanks!
> `[Button 1: Full Analytics Dekhein]`

### Odia (or)
> ନମସ୍କାର {{1}}! {{2}} ପାଇଁ ଆପଣଙ୍କ ବାଣୀ (Vaani) ROI Summary:
> 📊 ସମାଧାନ ହୋଇଥିବା କଲ୍ ଓ ଚାଟ୍: {{3}}
> 📅 ବୁକ୍ ହୋଇଥିବା ଅପଏଣ୍ଟମେଣ୍ଟ: {{4}}
> 🔄 ଉଦ୍ଧାର ହୋଇଥିବା ବୁକିଂ: {{5}} (ବ୍ୟସ୍ତ ସମୟ / ବନ୍ଦ ଥିବା ସମୟ)
> 💰 ଆନୁମାନିକ ଉଦ୍ଧାର ହୋଇଥିବା ରାଜସ୍ୱ: {{6}}
> ବାଣୀକୁ ଆପଣଙ୍କର AI ରିସେପସନିଷ୍ଟ ଭାବେ ବାଛିଥିବାରୁ ଧନ୍ୟବାଦ!
> `[Button 1: ସମ୍ପୂର୍ଣ୍ଣ ବିଶ୍ଳେଷଣ ଦେଖନ୍ତୁ]`

---

## 8. T_CSAT_REQUEST (In-Chat CSAT Feedback Request)
*   **Purpose:** Sent immediately after a staff handoff or bot conversation resolves.
*   **Variables:** `{{1}}` = Clinic/Doctor Name

### English (en)
> Thank you for contacting {{1}} 🙏 Did we resolve your query today? Please let us know your feedback by tapping a button:
> `[Button 1: 👍 Satisfied]` `[Button 2: 👎 Unsatisfied]`

### Hindi (hi)
> {{1}} से संपर्क करने के लिए धन्यवाद 🙏 क्या आज आपकी समस्या का समाधान हो पाया? कृपया नीचे बटन दबाकर अपनी प्रतिक्रिया (feedback) दें:
> `[Button 1: 👍 संतुष्ट]` `[Button 2: 👎 असंतुष्ट]`

### Hinglish (hi-Latn)
> {{1}} se contact karne ke liye thanks 🙏 Kya aaj aapki query solve ho gayi? Kripya neeche button daba kar apna feedback dein:
> `[Button 1: 👍 Satisfied]` `[Button 2: 👎 Unsatisfied]`

### Odia (or)
> {{1}} ସହିତ ଯୋଗାଯୋଗ କରିଥିବାରୁ ଧନ୍ୟବାଦ 🙏 ଆପଣଙ୍କ ସମସ୍ୟାର ସମାଧାନ ହୋଇପାରିଲା କି? ଦୟାକରି ତଳ ବଟନ୍ ଦବାଇ ଆପଣଙ୍କ ମତାମତ (feedback) ଦିଅନ୍ତୁ:
> `[Button 1: 👍 ସନ୍ତୁଷ୍ଟ]` `[Button 2: 👎 ଅସନ୍ତୁଷ୍ଟ]`
