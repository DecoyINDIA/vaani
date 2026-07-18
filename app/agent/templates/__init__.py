from __future__ import annotations

TEMPLATES = {
    "medical_refusal": {
        "en": "I apologize, but as an AI assistant, I cannot provide medical advice or diagnose symptoms. Please book an appointment to consult our dentist directly.",
        "hi": "मैं क्षमा चाहता हूँ, लेकिन एक एआई सहायक के रूप में, मैं चिकित्सा सलाह या निदान प्रदान नहीं कर सकता। कृपया हमारे दंत चिकित्सक से सीधे परामर्श करने के लिए एक अपॉइंटमेंट बुक करें।",
        "hi-Latn": "Main maafi chahta hoon, par ek AI assistant hone ke naate main medical advice ya ilaaj nahi bata sakta. Kripya humare dentist se direct consult karne ke liye appointment book karein.",
        "or": "ମୁଁ କ୍ଷମା ଚାହୁଁଛି, କିନ୍ତୁ ଏକ AI ସହାୟକ ଭାବରେ, ମୁଁ ଚିକିତ୍ସା ପରାମର୍ଶ କିମ୍ବା ରୋଗ ନିର୍ଣ୍ଣୟ ପ୍ରଦାନ କରିପାରିବି ନାହିଁ। ଦୟାକରି ଆମ ଦନ୍ତ ଚିକିତ୍ସକଙ୍କ ସହ ସିଧାସଳଖ ପରାମର୍ଶ କରିବା ପାଇଁ ଏକ ଅପଏଣ୍ଟମେଣ୍ଟ ବୁକ୍ କରନ୍ତୁ।"
    },
    "out_of_scope": {
        "en": "I'm sorry, I can only help you with dental clinic services, doctor details, hours, fees, and booking. Here is what I can do:\n1. Book an appointment\n2. Clinic timings\n3. Fees & Location\n4. Cancel/Reschedule",
        "hi": "क्षमा करें, मैं केवल दंत चिकित्सालय सेवाओं, चिकित्सक विवरण, समय, शुल्क और बुकिंग में आपकी सहायता कर सकता हूँ। मैं यह कर सकता हूँ:\n1. अपॉइंटमेंट बुक करें\n2. क्लिनिक का समय\n3. शुल्क और स्थान\n4. रद्द/पुनर्निर्धारित करें",
        "hi-Latn": "Sorry, main sirf dental clinic services, doctor info, timings, fees aur booking me aapki madad kar sakta hoon. Main ye sab kar sakta hoon:\n1. Appointment book karein\n2. Clinic timings\n3. Fees aur Location\n4. Cancel/Reschedule",
        "or": "ଦୟାକରି କ୍ଷମା କରିବେ, ମୁଁ କେବଳ ଦନ୍ତ ଚିକିତ୍ସାଳୟ ସେବା, ଡାକ୍ତରଙ୍କ ସୂଚନା, ସମୟ, ଶୁଳ୍କ ଏବଂ ବୁକିଂ ବିଷୟରେ ଆପଣଙ୍କୁ ସାହାଯ୍ୟ କରିପାରିବି। ମୁଁ ଏହି ସବୁ କରିପାରିବି:\n1. ଅପଏଣ୍ଟମେଣ୍ଟ ବୁକ୍ କରନ୍ତୁ\n2. କ୍ଲିନିକ୍ ସମୟ\n3. ଶୁଳ୍କ ଏବଂ ସ୍ଥାନ\n4. ବାତିଲ୍/ପୁନଃନିର୍ଦ୍ଧାରଣ"
    },
    "de_escalation": {
        "en": "I understand your concern. Please remain polite so I can assist you better. If you prefer, I can connect you to our clinic staff.",
        "hi": "मैं आपकी चिंता समझता हूँ। कृपया अभद्र भाषा का प्रयोग न करें ताकि मैं आपकी बेहतर सहायता कर सकूँ। यदि आप चाहें, तो मैं आपको हमारे क्लिनिक कर्मचारियों से जोड़ सकता हूँ।",
        "hi-Latn": "Main aapki chinta samajhta hoon. Kripya tameez se baat karein taaki main aapki sahi se madad kar sakoon. Agar aap chahein to main aapko clinic staff se connect kar sakta hoon.",
        "or": "ମୁଁ ଆପଣଙ୍କର ଚିନ୍ତା ବୁଝିପାରୁଛି। ଦୟାକରି ଶାନ୍ତ ରୁହନ୍ତୁ ଯଦ୍ୱାରା ମୁଁ ଆପଣଙ୍କୁ ଭଲ ଭାବରେ ସାହାଯ୍ୟ କରିପାରିବି। ଯଦି ଆପଣ ଚାହାଁନ୍ତି, ମୁଁ ଆପଣଙ୍କୁ ଆମର କ୍ଲିନିକ୍ କର୍ମଚାରୀଙ୍କ ସହିତ ସଂଯୋଗ କରିପାରିବି।"
    },
    "location_landmark": {
        "en": "Sharma Dental Clinic is located near Main Market, Bhubaneswar. Landmark: Opposite HDFC Bank. Location Pin: https://maps.google.com/?q=20.296,85.824",
        "hi": "शर्मा डेंटल क्लिनिक मुख्य बाजार, भुवनेश्वर के पास स्थित है। मील का पत्थर: एचडीएफसी बैंक के सामने। स्थान पिन: https://maps.google.com/?q=20.296,85.824",
        "hi-Latn": "Sharma Dental Clinic Main Market, Bhubaneswar ke paas hai. Landmark: HDFC Bank ke opposite. Location link: https://maps.google.com/?q=20.296,85.824",
        "or": "ଶର୍ମା ଡେଣ୍ଟାଲ୍ କ୍ଲିନିକ୍ ମୁଖ୍ୟ ବଜାର, ଭୁବନେଶ୍ୱର ନିକଟରେ ଅବସ୍ଥିତ। ଚିହ୍ନଟ ସ୍ଥାନ: HDFC ବ୍ୟାଙ୍କ ସମ୍ମୁଖରେ। ମାନଚିତ୍ର ଲିଙ୍କ: https://maps.google.com/?q=20.296,85.824"
    }
}


def get_template(name: str, lang: str) -> str:
    """Retrieve a template by name and language code. Falls back to English if missing."""
    template_data = TEMPLATES.get(name, {})
    return template_data.get(lang, template_data.get("en", ""))
