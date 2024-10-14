import os
import csv
from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from langchain.prompts import PromptTemplate
from langchain import LLMChain
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import plotly.express as px
import pandas as pd

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__, static_folder='static')  # Set the static folder


# Initialize MongoDB connection
mongo_uri = "MongoDB _KEY"
if mongo_uri is None:
    raise ValueError("MONGO_URI environment variable not set")

client = MongoClient(mongo_uri)
db = client['EXIT_SEVEN']  # Replace with your database name
collection = db['Traffic_Exit']  # Replace with your collection name

# Initialize ChatGroq LLM
groq_api_key = os.getenv("GROQ_API_KEY")  # Should be in your .env file
if groq_api_key is None:
    raise ValueError("GROQ_API_KEY environment variable not set")

llm = ChatGroq(
    model='llama3-70b-8192',
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    api_key=groq_api_key
)

# Function to generate a traffic report based on MongoDB data
def generate_traffic_report():
    try:
        latest_data = collection.find().sort('Timestamp', -1).limit(1)
        latest_data = list(latest_data)[0]  # Get the first (latest) document

        exit_name = latest_data.get('Exit')
        location = latest_data.get('Location')
        street = latest_data.get('Street')
        traffic_state = latest_data.get('Traffic State')
        gate_state = latest_data.get('Gate State')
        timestamp = latest_data.get('Timestamp')

        report = f"""
        ### Traffic Report for {exit_name}
        
        **Exit Name:** {exit_name}  
        **Traffic State:** {traffic_state}  
        **Location:** {location}  
        **Street:** {street}  
        **Gate State:** {gate_state}  
        **Time:** {timestamp}
        """
        return report
    except Exception as e:
        return f"Error reading the data: {str(e)}"

# Define prompt template for the chatbot
template = """
You are an AI assistant designed to provide traffic management information in a conversational and helpful way, you should speaking Arabic only, similar to ChatGPT. Your responses should be friendly, clear, and focused on the user's request.

Use the provided traffic data to give an accurate, concise, and helpful response.
If the data is unclear or missing, explain that to the user and offer suggestions if needed. Always aim to guide the user in a conversational and supportive manner.

You must not respond to any questions unrelated to traffic management information.
If a question does not pertain to traffic management information, respond with: "لا أستطيع تقديم معلومات حول هذا الموضوع. خبرتي تقتصر على معلومات إدارة حركة المرور."
  
Use the provided context to enhance your response, but do not rely solely on it.
If the context is insufficient or irrelevant, state: "بناءً على المعلومات المتاحة، لا أستطيع تقديم إجابة نهائية."

If user ask Is there a possibility of increasing the exit? should replay in feature

If user ask What are your future plans? anwser 1-I will report the time and peak times for each exit 2- Regular exit closing and opening times 3- Improve reporting

You should know the meaning between exit and film director

Structure your response clearly and concisely.
The response should without translate.

If the question is ambiguous or lacks clarity, request clarification.
For example: "لأقدم لك معلومات دقيقة، هل يمكنك إعادة صياغة سؤالك أو تقديم المزيد من التفاصيل حول [specific aspect]?"

Respond should like this format : Exit name and time and street and traffic state and gate state .
### Traffic Data:
{context}

### Question: {question}
---
### Response:
"""

prompt = PromptTemplate(
    input_variables=["context", "question"],
    template=template,
)

chain = LLMChain(llm=llm, prompt=prompt)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/dashboard')
def dashboard():
    latest_data = collection.find().sort('Timestamp', -1).limit(1)
    latest_data = list(latest_data)
    
    if latest_data:
        latest_exit = latest_data[0]

        exit_name = latest_exit.get('Exit')
        traffic_state = latest_exit.get('Traffic State')
        gate_state = latest_exit.get('Gate State')

        # Replace with actual latitude and longitude from your data if available
        latitude = 24.7136  
        longitude = 46.6753  

        df_exit = pd.DataFrame([{
            'Exit': exit_name,
            'Traffic State': traffic_state,
            'Vehicles Count': latest_exit.get('Vehicles Count'),
            'Gate State': gate_state,
            'latitude': latitude,
            'longitude': longitude
        }])

        fig = px.scatter_mapbox(
            df_exit, 
            lat='latitude', 
            lon='longitude', 
            size='Vehicles Count', 
            hover_data={
                'Exit': True,
                'Traffic State': True,
                'Vehicles Count': True
            },
            color_discrete_sequence=["red"], 
            size_max=15, 
            zoom=14, 
            mapbox_style="carto-positron"
        )

        map_html = fig.to_html(full_html=False)

        return render_template('dashboard.html', map_html=map_html, exit_name=exit_name, traffic_state=traffic_state, gate_state=gate_state)
    else:
        return render_template('dashboard.html', exit_name=None, traffic_state=None, gate_state=None)

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')

@app.route('/generate_report', methods=['POST'])
def generate_report():
    user_question = request.form.get("question")
    context = generate_traffic_report()
    
    response = chain.run(context=context, question=user_question)
    return jsonify({"response": response})

# Route to save feedback
@app.route('/save_feedback', methods=['POST'])
def save_feedback():
    feedback_data = request.get_json()
    question = feedback_data.get('question')
    response = feedback_data.get('response')
    is_like = feedback_data.get('like')

    # Save to CSV
    csv_file = 'chat_feedback.csv'
    file_exists = os.path.isfile(csv_file)

    with open(csv_file, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Question', 'Response', 'Like'])  # Write header if the file doesn't exist
        writer.writerow([question, response, is_like])  # Write the feedback

    return jsonify({'message': 'Feedback saved successfully.'})

@app.route('/Traffic_Exit')
def traffic_data():
    data = list(collection.find())
    if data:
        traffic_distribution = {}
        for record in data:
            state = record['Traffic State']
            traffic_distribution[state] = traffic_distribution.get(state, 0) + 1
        
        return jsonify({
            "data": data,
            "traffic_distribution": traffic_distribution
        })
    else:
        return jsonify({"error": "No traffic data found."}), 404

if __name__ == '__main__':
    app.run(debug=True)
