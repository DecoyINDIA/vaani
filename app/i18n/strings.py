"""String translation table for patient-facing WhatsApp flows (W2-01)."""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "booking.picker_prompt": {
        "en": "Choose a {service} time with {practitioner} on {date}.",
        "hi": "{date} को {practitioner} के साथ {service} के लिए समय चुनें।",
        "hi-Latn": "{date} ko {practitioner} ke saath {service} ke liye time chunein.",
        "or": "{date} ରେ {practitioner} ଙ୍କ ସହିତ {service} ପାଇଁ ସମୟ ବାଛନ୍ତୁ।",
    },
    "booking.confirm_prompt": {
        "en": "Confirm {service} with {practitioner} on {when}?",
        "hi": "क्या आप {when} पर {practitioner} के साथ {service} कन्फर्म करना चाहते हैं?",
        "hi-Latn": (
            "Kya aap {when} par {practitioner} ke saath {service} confirm karna chahte hain?"
        ),
        "or": "ଆପଣ {when} ରେ {practitioner} ଙ୍କ ସହିତ {service} ନିଶ୍ଚିତ କରିବାକୁ ଚାହାଁନ୍ତି କି?",
    },
    "booking.repick_prompt": {
        "en": "Please choose another appointment time.",
        "hi": "कृपया दूसरा अपॉइंटमेंट समय चुनें।",
        "hi-Latn": "Kripya doosra appointment time chunein.",
        "or": "ଦୟାକରି ଅନ୍ୟ ଏକ ଅପଏଣ୍ଟମେଣ୍ଟ ସମୟ ବାଛନ୍ତୁ।",
    },
    "booking.stale_selection": {
        "en": "That appointment is no longer in this selection. Please choose again.",
        "hi": "वह अपॉइंटमेंट अब इस चयन में उपलब्ध नहीं है। कृपया फिर से चुनें।",
        "hi-Latn": (
            "Woh appointment ab is selection me available nahi hai. Kripya dobara chunein."
        ),
        "or": "ସେହି ଅପଏଣ୍ଟମେଣ୍ଟ ଏହି ଚୟନରେ ଆଉ ଉପଲବ୍ଧ ନାହିଁ। ଦୟାକରି ପୁଣି ବାଛନ୍ତୁ।",
    },
    "booking.booked": {
        "en": "Your appointment is booked for {when}.",
        "hi": "आपका अपॉइंटमेंट {when} के लिए बुक हो गया है।",
        "hi-Latn": "Aapka appointment {when} ke liye book ho gaya hai.",
        "or": "ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ {when} ପାଇଁ ବୁକ୍ ହୋଇଯାଇଛି।",
    },
    "booking.rescheduled": {
        "en": "Your appointment is rescheduled for {when}.",
        "hi": "आपका अपॉइंटमेंट {when} के लिए रीशेड्यूल कर दिया गया है।",
        "hi-Latn": "Aapka appointment {when} ke liye reschedule kar diya gaya hai.",
        "or": "ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ {when} ପାଇଁ ରିସିଡ୍ୟୁଲ୍ ହୋଇଯାଇଛି।",
    },
    "booking.slot_taken_repick": {
        "en": "That slot was just taken. Please choose another appointment time.",
        "hi": "वह स्लॉट अभी किसी और ने ले लिया। कृपया दूसरा समय चुनें।",
        "hi-Latn": "Woh slot abhi kisi aur ne le liya. Kripya doosra appointment time chunein.",
        "or": "ସେହି ସ୍ଲଟ୍‌ଟି ବର୍ତ୍ତମାନ ବୁକ୍ ହୋଇଗଲା। ଦୟାକରି ଅନ୍ୟ ଏକ ସମୟ ବାଛନ୍ତୁ।",
    },
    "booking.slot_taken_none": {
        "en": (
            "That slot was just taken and no other offered time remains. "
            "Please ask for another date."
        ),
        "hi": (
            "वह स्लॉट अभी किसी और ने ले लिया और कोई अन्य समय उपलब्ध नहीं है। "
            "कृपया किसी अन्य तारीख के लिए पूछें।"
        ),
        "hi-Latn": (
            "Woh slot abhi kisi aur ne le liya aur koi doosra time available nahi hai. "
            "Kripya kisi doosri date ke liye poochein."
        ),
        "or": (
            "ସେହି ସ୍ଲଟ୍‌ଟି ବର୍ତ୍ତମାନ ବୁକ୍ ହୋଇଗଲା ଏବଂ ଅନ୍ୟ କୌଣସି ସମୟ ଉପଲବ୍ଧ ନାହିଁ। "
            "ଦୟାକରି ଅନ୍ୟ ଏକ ତାରିଖ ପାଇଁ ପଚାରନ୍ତୁ।"
        ),
    },
    "booking.already_confirmed": {
        "en": "Your appointment is already confirmed for {when}.",
        "hi": "आपका अपॉइंटमेंट पहले से ही {when} के लिए कन्फर्म है।",
        "hi-Latn": "Aapka appointment pehle se hi {when} ke liye confirmed hai.",
        "or": "ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ ପୂର୍ବରୁ {when} ପାଇଁ ନିଶ୍ଚିତ ହୋଇସାରିଛି।",
    },
    "booking.no_slots": {
        "en": "No appointments are available on {date}. Please send another day.",
        "hi": "{date} को कोई अपॉइंटमेंट उपलब्ध नहीं है। कृपया कोई दूसरा दिन बताएं।",
        "hi-Latn": (
            "{date} ko koi appointment available nahi hai. Kripya koi doosra din batayein."
        ),
        "or": "{date} ରେ କୌଣସି ଅପଏଣ୍ଟମେଣ୍ଟ ଉପଲବ୍ଧ ନାହିଁ। ଦୟାକରି ଅନ୍ୟ ଏକ ଦିନ ଜଣାନ୍ତୁ।",
    },
    "status.found": {
        "en": "Your appointment is {status} for {when}.",
        "hi": "आपका अपॉइंटमेंट {when} के लिए {status} है।",
        "hi-Latn": "Aapka appointment {when} ke liye {status} hai.",
        "or": "ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ {when} ପାଇଁ {status} ଅଛି।",
    },
    "status.none": {
        "en": "I could not find an active appointment for this WhatsApp number.",
        "hi": "मुझे इस व्हाट्सएप नंबर के लिए कोई सक्रिय अपॉइंटमेंट नहीं मिला।",
        "hi-Latn": "Mujhe is WhatsApp number ke liye koi active appointment nahi mila.",
        "or": "ମୁଁ ଏହି ହ୍ୱାଟ୍ସଆପ୍ ନମ୍ବର ପାଇଁ କୌଣସି ସକ୍ରିୟ ଅପଏଣ୍ଟମେଣ୍ଟ ପାଇଲି ନାହିଁ।",
    },
    "reschedule.none": {
        "en": "I could not find an active appointment to reschedule.",
        "hi": "मुझे रीशेड्यूल करने के लिए कोई सक्रिय अपॉइंटमेंट नहीं मिला।",
        "hi-Latn": "Mujhe reschedule karne ke liye koi active appointment nahi mila.",
        "or": "ମୁଁ ରିସିଡ୍ୟୁଲ୍ କରିବା ପାଇଁ କୌଣସି ସକ୍ରିୟ ଅପଏଣ୍ଟମେଣ୍ଟ ପାଇଲି ନାହିଁ।",
    },
    "cancel.prompt": {
        "en": "Cancel your appointment on {when}?",
        "hi": "क्या आप {when} का अपना अपॉइंटमेंट रद्द करना चाहते हैं?",
        "hi-Latn": "Kya aap {when} ka apna appointment cancel karna chahte hain?",
        "or": "ଆପଣ {when} ର ଅପଏଣ୍ଟମେଣ୍ଟ ବାତିଲ କରିବାକୁ ଚାହାଁନ୍ତି କି?",
    },
    "cancel.done": {
        "en": "Your appointment on {when} has been cancelled.",
        "hi": "{when} का आपका अपॉइंटमेंट रद्द कर दिया गया है।",
        "hi-Latn": "{when} ka aapka appointment cancel kar diya gaya hai.",
        "or": "{when} ର ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ ବାତିଲ କରାଯାଇଛି।",
    },
    "cancel.failed": {
        "en": "I could not cancel that appointment. Please contact the clinic.",
        "hi": "मैं वह अपॉइंटमेंट रद्द नहीं कर सका। कृपया क्लिनिक से संपर्क करें।",
        "hi-Latn": "Main woh appointment cancel nahi kar saka. Kripya clinic se contact karein.",
        "or": "ମୁଁ ସେହି ଅପଏଣ୍ଟମେଣ୍ଟ ବାତିଲ କରିପାରିଲି ନାହିଁ। ଦୟାକରି କ୍ଲିନିକ୍ ସହିତ ଯୋଗାଯୋଗ କରନ୍ତୁ।",
    },
    "cancel.kept": {
        "en": "Okay, your appointment is unchanged.",
        "hi": "ठीक है, आपका अपॉइंटमेंट यथावत है।",
        "hi-Latn": "Theek hai, aapka appointment unchanged hai.",
        "or": "ଠିକ୍ ଅଛି, ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ ଅପରିବର୍ତ୍ତିତ ରହିଲା।",
    },
    "optout.done": {
        "en": "You have been unsubscribed from automated reminders. Reply START to opt back in.",
        "hi": (
            "आपको स्वचालित रिमाइंडर्स से अनसब्सक्राइब कर दिया गया है। "
            "पुनः जुड़ने के लिए START लिखकर भेजें।"
        ),
        "hi-Latn": (
            "Aapko automated reminders se unsubscribe kar diya gaya hai. "
            "Dobara judne ke liye START reply karein."
        ),
        "or": (
            "ଆପଣଙ୍କୁ ସ୍ୱୟଂଚାଳିତ ରିମାଇଣ୍ଡରରୁ ଅନସବସ୍କ୍ରାଇବ୍ କରାଯାଇଛି। "
            "ପୁନର୍ବାର ସାମିଲ ହେବା ପାଇଁ START ଲେଖି ପଠାନ୍ତୁ।"
        ),
    },
    "optin.done": {
        "en": (
            "You have re-subscribed to appointment reminders. How can I help you today?"
        ),
        "hi": (
            "आपने अपॉइंटमेंट रिमाइंडर्स के लिए पुनः सब्सक्राइब कर लिया है। "
            "आज मैं आपकी क्या सहायता कर सकता हूँ?"
        ),
        "hi-Latn": (
            "Aapne appointment reminders dobara subscribe kar liya hai. "
            "Aaj main aapki kya madad kar sakta hu?"
        ),
        "or": (
            "ଆପଣ ଅପଏଣ୍ଟମେଣ୍ଟ ରିମାଇଣ୍ଡର ପାଇଁ ପୁନଃ ସବସ୍କ୍ରାଇବ୍ କରିଛନ୍ତି। "
            "ଆଜି ମୁଁ ଆପଣଙ୍କୁ କିପରି ସାହାଯ୍ୟ କରିପାରିବି?"
        ),
    },
    "media.unsupported": {
        "en": (
            "Sorry, I can only read text messages right now. "
            "Please type your question and I will help."
        ),
        "hi": (
            "क्षमा करें, मैं अभी केवल टेक्स्ट संदेश पढ़ सकता हूँ। "
            "कृपया अपना प्रश्न लिखकर भेजें और मैं आपकी सहायता करूँगा।"
        ),
        "hi-Latn": (
            "Sorry, main abhi sirf text messages padh sakta hu. "
            "Kripya apna sawaal type karein aur main madad karunga."
        ),
        "or": (
            "କ୍ଷମା କରିବେ, ମୁଁ ବର୍ତ୍ତମାନ କେବଳ ଟେକ୍ସଟ୍ ମେସେଜ୍ ପଢିପାରିବି। "
            "ଦୟାକରି ଆପଣଙ୍କ ପ୍ରଶ୍ନ ଟାଇପ୍ କରନ୍ତୁ ଏବଂ ମୁଁ ସାହାଯ୍ୟ କରିବି।"
        ),
    },
    "ui.choose_time": {
        "en": "Choose a time",
        "hi": "समय चुनें",
        "hi-Latn": "Time chunein",
        "or": "ସମୟ ବାଛନ୍ତୁ",
    },
    "ui.slots_title": {
        "en": "Available appointments",
        "hi": "उपलब्ध स्लॉट्स",
        "hi-Latn": "Available slots",
        "or": "ଉପଲବ୍ଧ ସମୟ",
    },
    "ui.confirm": {
        "en": "Confirm",
        "hi": "कन्फर्म करें",
        "hi-Latn": "Confirm karein",
        "or": "ନିଶ୍ଚିତ କରନ୍ତୁ",
    },
    "ui.choose_again": {
        "en": "Choose again",
        "hi": "फिर से चुनें",
        "hi-Latn": "Dobara chunein",
        "or": "ପୁଣି ବାଛନ୍ତୁ",
    },
    "ui.cancel_yes": {
        "en": "Yes, cancel",
        "hi": "हाँ, रद्द करें",
        "hi-Latn": "Haan, cancel karein",
        "or": "ହଁ, ବାତିଲ କରନ୍ତୁ",
    },
    "ui.cancel_keep": {
        "en": "Keep appointment",
        "hi": "रद्द न करें",
        "hi-Latn": "Keep booking",
        "or": "ବାତିଲ କରନ୍ତୁ ନାହିଁ",
    },
    "status.word.confirmed": {
        "en": "confirmed",
        "hi": "कन्फर्म",
        "hi-Latn": "confirmed",
        "or": "ନିଶ୍ଚିତ",
    },
    "status.word.rescheduled": {
        "en": "rescheduled",
        "hi": "रीशेड्यूल",
        "hi-Latn": "rescheduled",
        "or": "ରିସିଡ୍ୟୁଲ୍",
    },
    "menu.prompt": {
        "en": "Here is what I can help with:",
        "hi": "मैं इन चीज़ों में आपकी मदद कर सकता हूँ:",
        "hi-Latn": "Main in cheezon me aapki madad kar sakta hoon:",
        "or": "ମୁଁ ଏହି ସବୁ ବିଷୟରେ ସାହାଯ୍ୟ କରିପାରିବି:",
    },
    "menu.button": {
        "en": "Options",
        "hi": "विकल्प",
        "hi-Latn": "Options",
        "or": "ବିକଳ୍ପ",
    },
    "menu.book": {
        "en": "Book appointment",
        "hi": "अपॉइंटमेंट बुक करें",
        "hi-Latn": "Appointment book karein",
        "or": "ଅପଏଣ୍ଟମେଣ୍ଟ ବୁକ୍ କରନ୍ତୁ",
    },
    "menu.hours": {
        "en": "Clinic timings",
        "hi": "खुलने का समय",
        "hi-Latn": "Clinic timings",
        "or": "କ୍ଲିନିକ୍ ସମୟ",
    },
    "menu.location": {
        "en": "Location",
        "hi": "स्थान / पता",
        "hi-Latn": "Location",
        "or": "ଠିକଣା",
    },
    "menu.status": {
        "en": "My appointment",
        "hi": "मेरा अपॉइंटमेंट",
        "hi-Latn": "Mera appointment",
        "or": "ମୋର ଅପଏଣ୍ଟମେଣ୍ଟ",
    },
    "menu.human": {
        "en": "Talk to staff",
        "hi": "स्टाफ से बात करें",
        "hi-Latn": "Staff se baat karein",
        "or": "ଷ୍ଟାଫ୍ ସହ କଥା ହୁଅନ୍ତୁ",
    },
}
