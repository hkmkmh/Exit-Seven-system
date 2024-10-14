from locust import HttpUser, task, between

class TrafficUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def load_home(self):
        self.client.get('/')

    @task
    def load_dashboard(self):
        self.client.get('/dashboard')

    @task
    def generate_report(self):
        self.client.post('/generate_report', json={'question': 'What is the traffic state?'})
