# i18n Native-Speaker Review (W2-01)

This document catalogs all Hindi (`hi`, Devanagari) and Odia (`or`, Odia script) localized strings in Vaani for native-speaker review and sign-off prior to pilot deployment.

## Review Status
- **Date Generated:** 2026-11-12
- **Review Status:** Pending External Native-Speaker Sign-Off (Hindi & Odia)
- **Scope:** Deterministic patient-facing WhatsApp flow messages and UI labels (`app/i18n/strings.py`, `app/booking/timefmt.py`).

---

## Needs Native-Speaker Review

### 1. Booking Flow Messages

#### `booking.picker_prompt`
- **English:** `Choose a {service} time with {practitioner} on {date}.`
- **Hindi (`hi`):** `{date} को {practitioner} के साथ {service} के लिए समय चुनें।`
- **Odia (`or`):** `{date} ରେ {practitioner} ଙ୍କ ସହିତ {service} ପାଇଁ ସମୟ ବାଛନ୍ତୁ।`

#### `booking.confirm_prompt`
- **English:** `Confirm {service} with {practitioner} on {when}?`
- **Hindi (`hi`):** `क्या आप {when} पर {practitioner} के साथ {service} कन्फर्म करना चाहते हैं?`
- **Odia (`or`):** `ଆପଣ {when} ରେ {practitioner} ଙ୍କ ସହିତ {service} ନିଶ୍ଚିତ କରିବାକୁ ଚାହାଁନ୍ତି କି?`

#### `booking.repick_prompt`
- **English:** `Please choose another appointment time.`
- **Hindi (`hi`):** `कृपया दूसरा अपॉइंटमेंट समय चुनें।`
- **Odia (`or`):** `ଦୟାକରି ଅନ୍ୟ ଏକ ଅପଏଣ୍ଟମେଣ୍ଟ ସମୟ ବାଛନ୍ତୁ।`

#### `booking.stale_selection`
- **English:** `That appointment is no longer in this selection. Please choose again.`
- **Hindi (`hi`):** `वह अपॉइंटमेंट अब इस चयन में उपलब्ध नहीं है। कृपया फिर से चुनें।`
- **Odia (`or`):** `ସେହି ଅପଏଣ୍ଟମେଣ୍ଟ ଏହି ଚୟନରେ ଆଉ ଉପଲବ୍ଧ ନାହିଁ। ଦୟାକରି ପୁଣି ବାଛନ୍ତୁ।`

#### `booking.booked`
- **English:** `Your appointment is booked for {when}.`
- **Hindi (`hi`):** `आपका अपॉइंटमेंट {when} के लिए बुक हो गया है।`
- **Odia (`or`):** `ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ {when} ପାଇଁ ବୁକ୍ ହୋଇଯାଇଛି।`

#### `booking.rescheduled`
- **English:** `Your appointment is rescheduled for {when}.`
- **Hindi (`hi`):** `आपका अपॉइंटमेंट {when} के लिए रीशेड्यूल कर दिया गया है।`
- **Odia (`or`):** `ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ {when} ପାଇଁ ରିସିଡ୍ୟୁଲ୍ ହୋଇଯାଇଛି।`

#### `booking.slot_taken_repick`
- **English:** `That slot was just taken. Please choose another appointment time.`
- **Hindi (`hi`):** `वह स्लॉट अभी किसी और ने ले लिया। कृपया दूसरा समय चुनें।`
- **Odia (`or`):** `ସେହି ସ୍ଲଟ୍‌ଟି ବର୍ତ୍ତମାନ ବୁକ୍ ହୋଇଗଲା। ଦୟାକରି ଅନ୍ୟ ଏକ ସମୟ ବାଛନ୍ତୁ।`

#### `booking.slot_taken_none`
- **English:** `That slot was just taken and no other offered time remains. Please ask for another date.`
- **Hindi (`hi`):** `वह स्लॉट अभी किसी और ने ले लिया और कोई अन्य समय उपलब्ध नहीं है। कृपया किसी अन्य तारीख के लिए पूछें।`
- **Odia (`or`):** `ସେହି ସ୍ଲଟ୍‌ଟି ବର୍ତ୍ତମାନ ବୁକ୍ ହୋଇଗଲା ଏବଂ ଅନ୍ୟ କୌଣସି ସମୟ ଉପଲବ୍ଧ ନାହିଁ। ଦୟାକରି ଅନ୍ୟ ଏକ ତାରିଖ ପାଇଁ ପଚାରନ୍ତୁ।`

#### `booking.already_confirmed`
- **English:** `Your appointment is already confirmed for {when}.`
- **Hindi (`hi`):** `आपका अपॉइंटमेंट पहले से ही {when} के लिए कन्फर्म है।`
- **Odia (`or`):** `ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ ପୂର୍ବରୁ {when} ପାଇଁ ନିଶ୍ଚିତ ହୋଇସାରିଛି।`

#### `booking.no_slots`
- **English:** `No appointments are available on {date}. Please send another day.`
- **Hindi (`hi`):** `{date} को कोई अपॉइंटमेंट उपलब्ध नहीं है। कृपया कोई दूसरा दिन बताएं।`
- **Odia (`or`):** `{date} ରେ କୌଣସି ଅପଏଣ୍ଟମେଣ୍ଟ ଉପଲବ୍ଧ ନାହିଁ। ଦୟାକରି ଅନ୍ୟ ଏକ ଦିନ ଜଣାନ୍ତୁ।`

---

### 2. Status & Reschedule Messages

#### `status.found`
- **English:** `Your appointment is {status} for {when}.`
- **Hindi (`hi`):** `आपका अपॉइंटमेंट {when} के लिए {status} है।`
- **Odia (`or`):** `ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ {when} ପାଇଁ {status} ଅଛି।`

#### `status.none`
- **English:** `I could not find an active appointment for this WhatsApp number.`
- **Hindi (`hi`):** `मुझे इस व्हाट्सएप नंबर के लिए कोई सक्रिय अपॉइंटमेंट नहीं मिला।`
- **Odia (`or`):** `ମୁଁ ଏହି ହ୍ୱାଟ୍ସଆପ୍ ନମ୍ବର ପାଇଁ କୌଣସି ସକ୍ରିୟ ଅପଏଣ୍ଟମେଣ୍ଟ ପାଇଲି ନାହିଁ।`

#### `reschedule.none`
- **English:** `I could not find an active appointment to reschedule.`
- **Hindi (`hi`):** `मुझे रीशेड्यूल करने के लिए कोई सक्रिय अपॉइंटमेंट नहीं मिला।`
- **Odia (`or`):** `ମୁଁ ରିସିଡ୍ୟୁଲ୍ କରିବା ପାଇଁ କୌଣସି ସକ୍ରିୟ ଅପଏଣ୍ଟମେଣ୍ଟ ପାଇଲି ନାହିଁ।`

#### `status.word.confirmed`
- **English:** `confirmed`
- **Hindi (`hi`):** `कन्फर्म`
- **Odia (`or`):** `ନିଶ୍ଚିତ`

#### `status.word.rescheduled`
- **English:** `rescheduled`
- **Hindi (`hi`):** `रीशेड्यूल`
- **Odia (`or`):** `ରିସିଡ୍ୟୁଲ୍`

---

### 3. Cancellation Flow Messages

#### `cancel.prompt`
- **English:** `Cancel your appointment on {when}?`
- **Hindi (`hi`):** `क्या आप {when} का अपना अपॉइंटमेंट रद्द करना चाहते हैं?`
- **Odia (`or`):** `ଆପଣ {when} ର ଅପଏଣ୍ଟମେଣ୍ଟ ବାତିଲ କରିବାକୁ ଚାହାଁନ୍ତି କି?`

#### `cancel.done`
- **English:** `Your appointment on {when} has been cancelled.`
- **Hindi (`hi`):** `{when} का आपका अपॉइंटमेंट रद्द कर दिया गया है।`
- **Odia (`or`):** `{when} ର ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ ବାତିଲ କରାଯାଇଛି।`

#### `cancel.failed`
- **English:** `I could not cancel that appointment. Please contact the clinic.`
- **Hindi (`hi`):** `मैं वह अपॉइंटमेंट रद्द नहीं कर सका। कृपया क्लिनिक से संपर्क करें।`
- **Odia (`or`):** `ମୁଁ ସେହି ଅପଏଣ୍ଟମେଣ୍ଟ ବାତିଲ କରିପାରିଲି ନାହିଁ। ଦୟାକରି କ୍ଲିନିକ୍ ସହିତ ଯୋଗାଯୋଗ କରନ୍ତୁ।`

#### `cancel.kept`
- **English:** `Okay, your appointment is unchanged.`
- **Hindi (`hi`):** `ठीक है, आपका अपॉइंटमेंट यथावत है।`
- **Odia (`or`):** `ଠିକ୍ ଅଛି, ଆପଣଙ୍କ ଅପଏଣ୍ଟମେଣ୍ଟ ଅପରିବର୍ତ୍ତିତ ରହିଲା।`

---

### 4. Opt-Out / Opt-In & Media Messages

#### `optout.done`
- **English:** `You have been unsubscribed from automated reminders. Reply START to opt back in.`
- **Hindi (`hi`):** `आपको स्वचालित रिमाइंडर्स से अनसब्सक्राइब कर दिया गया है। पुनः जुड़ने के लिए START लिखकर भेजें।`
- **Odia (`or`):** `ଆପଣଙ୍କୁ ସ୍ୱୟଂଚାଳିତ ରିମାଇଣ୍ଡରରୁ ଅନସବସ୍କ୍ରାଇବ୍ କରାଯାଇଛି। ପୁନର୍ବାର ସାମିଲ ହେବା ପାଇଁ START ଲେଖି ପଠାନ୍ତୁ।`

#### `optin.done`
- **English:** `You have re-subscribed to appointment reminders. How can I help you today?`
- **Hindi (`hi`):** `आपने अपॉइंटमेंट रिमाइंडर्स के लिए पुनः सब्सक्राइब कर लिया है। आज मैं आपकी क्या सहायता कर सकता हूँ?`
- **Odia (`or`):** `ଆପଣ ଅପଏଣ୍ଟମେଣ୍ଟ ରିମାଇଣ୍ଡର ପାଇଁ ପୁନଃ ସବସ୍କ୍ରାଇବ୍ କରିଛନ୍ତି। ଆଜି ମୁଁ ଆପଣଙ୍କୁ କିପରି ସାହାଯ୍ୟ କରିପାରିବି?`

#### `media.unsupported`
- **English:** `Sorry, I can only read text messages right now. Please type your question and I will help.`
- **Hindi (`hi`):** `क्षमा करें, मैं अभी केवल टेक्स्ट संदेश पढ़ सकता हूँ। कृपया अपना प्रश्न लिखकर भेजें और मैं आपकी सहायता करूँगा।`
- **Odia (`or`):** `କ୍ଷମା କରିବେ, ମୁଁ ବର୍ତ୍ତମାନ କେବଳ ଟେକ୍ସଟ୍ ମେସେଜ୍ ପଢିପାରିବି। ଦୟାକରି ଆପଣଙ୍କ ପ୍ରଶ୍ନ ଟାଇପ୍ କରନ୍ତୁ ଏବଂ ମୁଁ ସାହାଯ୍ୟ କରିବି।`

---

### 5. Interactive UI Element Titles (WhatsApp Character Limits)

| Key | Max Chars | English | Hindi (`hi`) | Odia (`or`) |
|---|---|---|---|---|
| `ui.choose_time` | 20 | `Choose a time` | `समय चुनें` (9) | `ସମୟ ବାଛନ୍ତୁ` (11) |
| `ui.slots_title` | 24 | `Available appointments` | `उपलब्ध स्लॉट्स` (13) | `ଉପଲବ୍ଧ ସମୟ` (10) |
| `ui.confirm` | 20 | `Confirm` | `कन्फर्म करें` (11) | `ନିଶ୍ଚିତ କରନ୍ତୁ` (13) |
| `ui.choose_again` | 20 | `Choose again` | `फिर से चुनें` (12) | `ପୁଣି ବାଛନ୍ତୁ` (11) |
| `ui.cancel_yes` | 20 | `Yes, cancel` | `हाँ, रद्द करें` (13) | `ହଁ, ବାତିଲ କରନ୍ତୁ` (15) |
| `ui.cancel_keep` | 20 | `Keep appointment` | `रद्द न करें` (10) | `ବାତିଲ କରନ୍ତୁ ନାହିଁ` (18) |

---

### 6. Date/Time Abbreviations (`app/booking/timefmt.py`)

#### Hindi Weekday Abbreviations (`HI_WEEKDAYS`):
- `0`: `सोम`
- `1`: `मंगल`
- `2`: `बुध`
- `3`: `गुरु`
- `4`: `शुक्र`
- `5`: `शनि`
- `6`: `रवि`

#### Hindi Month Abbreviations (`HI_MONTHS`):
- `1`..`12`: `जन`, `फ़र`, `मार्च`, `अप्रैल`, `मई`, `जून`, `जुल`, `अग`, `सित`, `अक्टू`, `नव`, `दिस`

#### Odia Weekday Abbreviations (`OR_WEEKDAYS`):
- `0`: `ସୋମ`
- `1`: `ମଙ୍ଗଳ`
- `2`: `ବୁଧ`
- `3`: `ଗୁରୁ`
- `4`: `ଶୁକ୍ର`
- `5`: `ଶନି`
- `6`: `ରବି`

*Note: In Odia format, numeric month is used (`<weekday> DD/MM, hh:mm AM/PM`), ensuring all strings strictly remain under 24 characters.*

---

### 7. Interactive Capability Menu Elements (W2-09)

| Key | Max Chars | English | Hindi (`hi`) | Hinglish (`hi-Latn`) | Odia (`or`) |
|---|---|---|---|---|---|
| `menu.prompt` | - | `Here is what I can help with:` | `मैं इन चीज़ों में आपकी मदद कर सकता हूँ:` | `Main in cheezon me aapki madad kar sakta hoon:` | `ମୁଁ ଏହି ସବୁ ବିଷୟରେ ସାହାଯ୍ୟ କରିପାରିବି:` |
| `menu.button` | 20 | `Options` | `विकल्प` (6) | `Options` (7) | `ବିକଳ୍ପ` (6) |
| `menu.book` | 24 | `Book appointment` | `अपॉइंटमेंट बुक करें` (19) | `Appointment book karein` (23) | `ଅପଏଣ୍ଟମେଣ୍ଟ ବୁକ୍ କରନ୍ତୁ` (23) |
| `menu.hours` | 24 | `Clinic timings` | `खुलने का समय` (12) | `Clinic timings` (14) | `କ୍ଲିନିକ୍ ସମୟ` (12) |
| `menu.location` | 24 | `Location` | `स्थान / पता` (11) | `Location` (8) | `ଠିକଣା` (5) |
| `menu.status` | 24 | `My appointment` | `मेरा अपॉइंटमेंट` (16) | `Mera appointment` (16) | `ମୋର ଅପଏଣ୍ଟମେଣ୍ଟ` (16) |
| `menu.human` | 24 | `Talk to staff` | `स्टाफ से बात करें` (18) | `Staff se baat karein` (20) | `ଷ୍ଟାଫ୍ ସହ କଥା ହୁଅନ୍ତୁ` (21) |

