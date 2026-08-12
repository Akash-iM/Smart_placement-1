import os

views_path = r'c:\Users\Praveen\Downloads\SPC\students\views.py'

with open(views_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_chatbot_code = """
from openai import OpenAI

@login_required
def chatbot(request):
    if not request.session.get('chat_history'):
        request.session['chat_history'] = [
            {"role": "system", "content": "You are a friendly, encouraging interview coach. Provide concise, actionable advice."}
        ]
        
    # If the user wants to clear the chat
    if request.method == "POST" and request.POST.get("action") == "clear":
        request.session['chat_history'] = [
            {"role": "system", "content": "You are a friendly, encouraging interview coach. Provide concise, actionable advice."}
        ]
        request.session.modified = True
        return redirect('students:chatbot')
        
    if request.method == "POST":
        user_message = request.POST.get("message", "").strip()
        if user_message:
            chat_history = request.session.get('chat_history', [])
            chat_history.append({"role": "user", "content": user_message})
            
            try:
                client = OpenAI(api_key=getattr(settings, 'OPENAI_API_KEY', ''))
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=chat_history
                )
                ai_response = completion.choices[0].message.content
                chat_history.append({"role": "assistant", "content": ai_response})
            except Exception as e:
                ai_response = f"I'm sorry, I'm having trouble connecting to my service right now. Please check your API key setup. ({str(e)})"
                chat_history.append({"role": "assistant", "content": ai_response})
                
            request.session['chat_history'] = chat_history
            request.session.modified = True
            
        return redirect('students:chatbot')

    chat_history = request.session.get('chat_history', [])
    display_history = [m for m in chat_history if m['role'] != 'system']
    
    return render(request, "students/chatbot.html", {"chat_history": display_history})
"""

# Slice out lines 363 to end (0-indexed, so we keep lines[:362])
clean_lines = lines[:362]

with open(views_path, 'w', encoding='utf-8') as f:
    f.writelines(clean_lines)
    f.write(new_chatbot_code)

print("Successfully cleaned up views.py and appended enhanced chatbot.")
