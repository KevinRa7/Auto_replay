import json
import requests
from flask import Flask, request
import re

app = Flask(__name__)

ACCESS_TOKEN = "EAAS7rDXPZAAwBPA3TNynWn8TrFPQehnMt9SXW2wh678RjHNa6B5VRZAHevYtgp9XaIcCzQEFjPPfpYWKRsP4cO3Rt5DlYrfeXJuGq2ByTaJieCDfBYFaLVFTuLLMWZAma7iNwjihsFE47eet1ZBo7A4Qw1puVpr0bmn8qWbEr2iNazQT4q5jIUnat5SgYZAjzwZBE80wgZD"
VERIFY_TOKEN = "webnex_ig_webhook"
YOUR_SERVER_API_URL = "https://supportengine.webnexs.com/admin/user-enquiry"

# ✅ Your Instagram account/page ID
MY_IG_ID = "17841454891845744"  # Replace with actual ID from /me API

def clean_text(raw_result):
    """Clean and format server reply text without breaking words."""
    
    text = raw_result.replace("\\n", " ").replace("\n", " ")
    text = re.sub(r'\s+', ' ', text).strip()

    text = text.replace("●", "\n•")
    text = text.replace("➔ Action:", "\n\n**Action:**")
    for keyword in ["USER DETAILS", "Address Fields:", "visibility and lifecycle state", "Address Fields"]:
        text = text.replace(keyword, f"\n\n**{keyword}**")

    text = re.sub(r'(\.\s+)([A-Z])([a-z])', r'\1\n\2\3', text)

    # Force numbered steps onto new lines
    text = re.sub(r'(\s)(\d+\.\s)', r'\n\2', text)

    # Split into safe chunks
    max_len = 1000
    chunks = []
    start = 0

    while start < len(text):
        if len(text) - start <= max_len:
            chunks.append(text[start:].strip())
            break

        cut_pos = start + max_len
        while cut_pos > start and text[cut_pos - 1] != " ":
            cut_pos -= 1

        if cut_pos == start:
            cut_pos = start + max_len

        chunks.append(text[start:cut_pos].strip())
        start = cut_pos

    # Merge very small last chunk
    if len(chunks) > 1 and len(chunks[-1]) < 50:
        if len(chunks[-2]) + 1 + len(chunks[-1]) <= max_len:
            chunks[-2] = chunks[-2] + " " + chunks[-1]
            chunks.pop()

    return chunks 





@app.route("/")
def home():
    return "<p>Instagram DM Webhook with External Reply Server</p>"



def send_comment_reply(comment_id, reply_chunks):
    """Reply to an Instagram post comment."""
    url = f"https://graph.facebook.com/v21.0/{comment_id}/replies"
    headers = {"Content-Type": "application/json"}
    payload = {
            "message": ''.join(reply_chunks),
            "access_token": ACCESS_TOKEN
        }
    response = requests.post(url, headers=headers, json=payload)
    print(f"💬 Sent comment reply → Status: {response.status_code}")
    if response.status_code != 200:
        print("❌ Error sending comment reply:", response.text)


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if token == VERIFY_TOKEN:
            return challenge, 200
        return "Verification token mismatch", 403

    if request.method == "POST":
        data = request.get_json()
        print("📩 Incoming Webhook:")
        print(json.dumps(data, indent=4))

        for entry in data.get("entry", []):
            
            # ✅ Handle Instagram DMs
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                message_text = messaging_event.get("message", {}).get("text")

                if sender_id == MY_IG_ID:
                    continue

                if sender_id and message_text:
                    reply_text = get_reply_from_server(message_text)
                    send_reply(sender_id, reply_text)

            # ✅ Handle Instagram Post Comments
            for change in entry.get("changes", []):
                if change.get("field") == "comments":
                    comment = change["value"]
                    comment_id = comment.get("id")
                    comment_text = comment.get("text")

                    # if comment_id == MY_IG_comment_id:
                        # continue
                    if comment_id and comment_text:
                        # Ignore your own comments to prevent reply loops
                        if comment.get("from", {}).get("id") == MY_IG_ID:
                            continue

                        send_comment_reply(comment_id, ['Thank you for your comment! We will get back to you soon.'])


        return "ok", 200


def get_reply_from_server(user_message):
    try:
        payload = {
            "project_name": "wcart",
            "prompt": user_message
        }
        headers = {"Content-Type": "application/json"}
        response = requests.post(YOUR_SERVER_API_URL, headers=headers, json=payload)

        data = response.json()
        print("📥 Response from your server:", data)

        raw_text = data.get("result", "Sorry, I couldn't get a reply right now.")
        return clean_text(raw_text)  # ✅ now returns a list of chunks

    except Exception as e:
        print("❌ Error contacting server:", e)
        return ["Sorry, something went wrong while getting a reply."]



def send_reply(recipient_id, message_chunks):
    """Send a message back to the Instagram user, already split into safe chunks."""
    url = f"https://graph.facebook.com/v21.0/me/messages?access_token={ACCESS_TOKEN}"
    headers = {"Content-Type": "application/json"}

    for chunk in message_chunks:
        payload = {
            "messaging_product": "instagram",
            "recipient": {"id": recipient_id},
            "message": {"text": chunk}
        }

        response = requests.post(url, headers=headers, json=payload)
        print(f"📤 Sent chunk ({len(chunk)} chars) → Status: {response.status_code}")
        if response.status_code != 200:
            print("❌ Error sending message:", response.text)

if __name__ == "__main__":
    app.run(port=5000,debug=False)
