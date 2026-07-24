from app import create_app, db
from app.utils.startup_cleanup import cleanup_test_data

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {'app': app, 'db': db}


if __name__ == '__main__':
    with app.app_context():
        result = cleanup_test_data(app.config.get('UPLOAD_FOLDER'))
        print(f"[startup-cleanup] removed test data: {result}")
    app.run(host='0.0.0.0', port=5000)
