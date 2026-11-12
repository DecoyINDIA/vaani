from __future__ import annotations

# Static, pre-approved replies. Wording is industry-neutral on purpose: these
# are sent for every tenant, so they must not assume a kind of business.
TEMPLATES = {
    "handoff_ack": {
        "en": "I have handed this conversation to our team. They will reply here.",
        "hi": "मैंने यह बातचीत हमारी टीम को सौंप दी है। वे यहीं जवाब देंगे।",
        "hi-Latn": "Maine yeh conversation hamari team ko hand off kar di hai. Woh yahin reply karenge.",
        "or": "ମୁଁ ଏହି କଥୋପକଥନଟି ଆମ ଟିମ୍‌କୁ ଦେଇଛି। ସେମାନେ ଏଠାରେ ଉତ୍ତର ଦେବେ।",
    },
    "handoff_after_hours": {
        "en": "Our team is available from our next opening time. Your message is queued for them, and I can still help you book an appointment meanwhile.",
        "hi": "हमारी टीम अगले खुलने के समय उपलब्ध होगी। आपका संदेश टीम के लिए कतार में है; इस बीच मैं अपॉइंटमेंट बुक करने में मदद कर सकता हूँ।",
        "hi-Latn": "Hamari team agle opening time par available hogi. Aapka message team ke liye queue mein hai; tab tak main appointment book karne mein madad kar sakta hoon.",
        "or": "ଆମ ଟିମ୍ ପରବର୍ତ୍ତୀ ଥର ଖୋଲିବାବେଳେ ଉପଲବ୍ଧ ହେବ। ଆପଣଙ୍କ ସନ୍ଦେଶ ଟିମ୍ ପାଇଁ ଧାଡ଼ିରେ ଅଛି; ସେପର୍ଯ୍ୟନ୍ତ ମୁଁ ଅପଏଣ୍ଟମେଣ୍ଟ ବୁକ୍ କରିବାରେ ସାହାଯ୍ୟ କରିପାରିବି।",
    },
    "restricted_advice_refusal": {
        "en": "I'm sorry, but as an AI assistant I can't give advice on this. I'm passing your question to our team, and you can also book an appointment to discuss it with them directly.",
        "hi": "क्षमा करें, एक एआई सहायक होने के नाते मैं इस विषय पर सलाह नहीं दे सकता। मैं आपका प्रश्न हमारी टीम तक पहुँचा रहा हूँ; आप उनसे सीधे बात करने के लिए अपॉइंटमेंट भी बुक कर सकते हैं।",
        "hi-Latn": "Maaf kijiye, ek AI assistant hone ke naate main is vishay par salah nahi de sakta. Main aapka sawaal hamari team tak pahuncha raha hoon; aap unse seedhe baat karne ke liye appointment bhi book kar sakte hain.",
        "or": "କ୍ଷମା କରିବେ, ଏକ AI ସହାୟକ ଭାବରେ ମୁଁ ଏହି ବିଷୟରେ ପରାମର୍ଶ ଦେଇପାରିବି ନାହିଁ। ମୁଁ ଆପଣଙ୍କ ପ୍ରଶ୍ନ ଆମ ଟିମ୍‌କୁ ପଠାଉଛି; ସେମାନଙ୍କ ସହ ସିଧାସଳଖ କଥା ହେବା ପାଇଁ ଆପଣ ଅପଏଣ୍ଟମେଣ୍ଟ ମଧ୍ୟ ବୁକ୍ କରିପାରିବେ।",
    },
    "out_of_scope": {
        "en": "I'm sorry, I can only help with our services, team details, hours, fees, and booking. Here is what I can do:\n1. Book an appointment\n2. Opening hours\n3. Fees & Location\n4. Cancel/Reschedule",
        "hi": "क्षमा करें, मैं केवल हमारी सेवाओं, टीम की जानकारी, समय, शुल्क और बुकिंग में आपकी सहायता कर सकता हूँ। मैं यह कर सकता हूँ:\n1. अपॉइंटमेंट बुक करें\n2. खुलने का समय\n3. शुल्क और स्थान\n4. रद्द/पुनर्निर्धारित करें",
        "hi-Latn": "Sorry, main sirf hamari services, team ki jaankari, timings, fees aur booking me aapki madad kar sakta hoon. Main ye sab kar sakta hoon:\n1. Appointment book karein\n2. Timings\n3. Fees aur Location\n4. Cancel/Reschedule",
        "or": "ଦୟାକରି କ୍ଷମା କରିବେ, ମୁଁ କେବଳ ଆମର ସେବା, ଟିମ୍ ସୂଚନା, ସମୟ, ଶୁଳ୍କ ଏବଂ ବୁକିଂ ବିଷୟରେ ଆପଣଙ୍କୁ ସାହାଯ୍ୟ କରିପାରିବି। ମୁଁ ଏହି ସବୁ କରିପାରିବି:\n1. ଅପଏଣ୍ଟମେଣ୍ଟ ବୁକ୍ କରନ୍ତୁ\n2. ଖୋଲିବା ସମୟ\n3. ଶୁଳ୍କ ଏବଂ ସ୍ଥାନ\n4. ବାତିଲ୍/ପୁନଃନିର୍ଦ୍ଧାରଣ",
    },
    "de_escalation": {
        "en": "I understand your concern. Please remain polite so I can assist you better. If you prefer, I can connect you to our team.",
        "hi": "मैं आपकी चिंता समझता हूँ। कृपया अभद्र भाषा का प्रयोग न करें ताकि मैं आपकी बेहतर सहायता कर सकूँ। यदि आप चाहें, तो मैं आपको हमारी टीम से जोड़ सकता हूँ।",
        "hi-Latn": "Main aapki chinta samajhta hoon. Kripya tameez se baat karein taaki main aapki sahi se madad kar sakoon. Agar aap chahein to main aapko hamari team se connect kar sakta hoon.",
        "or": "ମୁଁ ଆପଣଙ୍କର ଚିନ୍ତା ବୁଝିପାରୁଛି। ଦୟାକରି ଶାନ୍ତ ରୁହନ୍ତୁ ଯଦ୍ୱାରା ମୁଁ ଆପଣଙ୍କୁ ଭଲ ଭାବରେ ସାହାଯ୍ୟ କରିପାରିବି। ଯଦି ଆପଣ ଚାହାଁନ୍ତି, ମୁଁ ଆପଣଙ୍କୁ ଆମ ଟିମ୍ ସହିତ ସଂଯୋଗ କରିପାରିବି।",
    },
}


def get_template(name: str, lang: str) -> str:
    """Retrieve a template by name and language code. Falls back to English if missing."""
    template_data = TEMPLATES.get(name, {})
    return template_data.get(lang, template_data.get("en", ""))
