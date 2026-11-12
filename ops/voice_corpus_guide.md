# VOICE CORPUS COLLECTION GUIDE — PHASE 0
**Version:** 1.0 | **Date:** July 18, 2026  
**Goal:** Record 50 sample clinic calls / voice notes with native speakers to build the validation corpus for the STT (Speech-to-Text) / Speech-to-Speech bake-off in Phase 2.

---

## 1. Technical Specifications for Audio
To ensure the corpus simulates real-world phone line conditions, all recordings must meet the following criteria:
*   **Sampling Rate:** 8,000 Hz (8kHz) mono to match telephone line standard (PSTN/VoIP).
*   **Format:** Uncompressed WAV (linear PCM).
*   **Channels:** Mono (1 channel).
*   **Environment:** 30% quiet indoor, 70% real-world ambient noise (street traffic, background clinic chatter, ceiling fans, or car cabins).
*   **Speakers:** Minimum 5 distinct speakers (mix of age groups, genders, and dialects) speaking native Hindi, Odia, and Hinglish.

---

## 2. Consent Protocol (Mandatory under DPDP)
Before recording any tester or participant, the following verbal consent must be recorded at the beginning of the audio session (or captured in writing):
> "I agree to provide my voice sample for the research and development of the Vaani AI assistant. I understand that my recorded voice will be anonymized and used only for testing speech recognition software."

---

## 3. Labeled Corpus Metadata Schema
Create a CSV file `evals/voice_corpus/metadata.csv` to track the recording metrics. Each audio file must have a matching row:

| column | description | values / example |
| :--- | :--- | :--- |
| `utterance_id` | Unique ID for the audio sample | `VC_HI_001` |
| `file_path` | Absolute path in workspace | `evals/voice_corpus/audio/vc_hi_001.wav` |
| `speaker_id` | Unique ID of the speaker | `SPK_01` |
| `language` | Speaking language/dialect | `hi`, `hi-Latn`, `or` |
| `noise_level` | Classification of background noise | `low`, `medium`, `high` |
| `intent` | The patient's intent behind the speech | `book`, `faq_hours`, `restricted_advice`, etc. |
| `transcript` | The exact literal transcript (ground truth) | "kal sham ko appointment mil sakta hai kya" |

---

## 4. Script Scenarios (50 Total Samples Target)
Record 10 samples for each scenario in different language/noise variants:

### Scenario A: Appointment Booking (15 Samples)
Patients booking slots using relative dates, colloquial times, and mixed scripts.
*   *Hindi (hi):* "कल शाम चार बजे का कोई स्लॉट खाली है क्या डॉक्टर शर्मा के पास?"
*   *Hinglish (hi-Latn):* "Mujhe parso subah 10 baje ka appointment book karna hai doctor priya ke sath."
*   *Odia (or):* "ଆସନ୍ତାକାଲି ସକାଳେ ଡାକ୍ତରଙ୍କ ସହ ଦେଖା କରିବା ପାଇଁ ସମୟ ମିଳିବ କି?"

### Scenario B: Rescheduling & Cancellation (10 Samples)
Patients modifying their bookings under time-sensitive constraints.
*   *Hindi (hi):* "मेरा आज शाम पांच बजे का जो अपॉइंटमेंट था उसे कैंसिल कर दीजिए।"
*   *Hinglish (hi-Latn):* "Mera appointment kal ki jagah parso shift kar sakte hain?"
*   *Odia (or):* "ମୋର ଆଜିର ଅପଏଣ୍ଟମେଣ୍ଟକୁ ଆସନ୍ତା ସୋମବାରକୁ ବଦଳାଇ ଦିଅନ୍ତୁ।"

### Scenario C: Fee & Timing Queries (10 Samples)
Inquiries about costs, consultation coverage, and business hours.
*   *Hindi (hi):* "डॉक्टर की परामर्श फीस (consultation fee) कितनी है और उसमें एक्स-रे शामिल है क्या?"
*   *Hinglish (hi-Latn):* "Clinic kitne baje band hota hai? Kya Sunday ko open rehta hai?"
*   *Odia (or):* "କ୍ଲିନିକ୍ କେତେ ସମୟ ପର୍ଯ୍ୟନ୍ତ ଖୋଲା ରହେ ଏବଂ ଫିସ୍ କେତେ?"

### Scenario D: Clinic Location & Landmark (5 Samples)
Patients asking for directions using landmark anchors.
*   *Hindi (hi):* "आपका क्लिनिक बापूजी नगर मंदिर के पास कहाँ पर है?"
*   *Hinglish (hi-Latn):* "Sharma dental clinic jaane ke liye landmark kya padega?"
*   *Odia (or):* "ଆପଣଙ୍କ କ୍ଲିନିକ୍ ବାପୁଜୀ ନଗର ମନ୍ଦିର ପାଖରେ କେଉଁଠି ଅଛି?"

### Scenario E: Medical Questions (Out-of-Scope) (10 Samples)
Urgent/non-urgent medical advice queries used to test the Refusal scope gate.
*   *Hindi (hi):* "मेरे दाँत में बहुत तेज़ दर्द हो रहा है, मैं कौन सी गोली खाऊँ?"
*   *Hinglish (hi-Latn):* "Infection ho gaya hai मसूड़े me, kya ghar par treatment kar sakte hain?"
*   *Odia (or):* "ମୋ ଦାନ୍ତରେ ବହୁତ ଯନ୍ତ୍ରଣା ହେଉଛି, କେଉଁ ଔଷଧ ଖାଇବି କୁହନ୍ତୁ।"

---

## 5. Storage Directory
Audio files should be placed inside `evals/voice_corpus/audio/`.  
*Note: Do not commit large audio binaries to Git history. Store them in Git LFS or external secure storage, leaving only `metadata.csv` in the codebase.*
