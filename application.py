# This file is required for AWS Elastic Beanstalk
# It tells EB which WSGI application to run

from app import app

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=False)
