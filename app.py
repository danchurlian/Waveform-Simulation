from flask import Flask, render_template, request

app = Flask(__name__)

if __name__ == "__main__":
    print("Running")
    app.run()