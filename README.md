Welcome to the **Axies** project! This repository includes the Axies web application written on Flask.

## Instructions for setting up the web application
**Note:** These instructions are for development purpose only; **not for production** deployment.
1. Clone the repository, create a Python 3.7 virtual environment, and install the requirements in the [requirements.txt](requirements.txt) file:
   ``` pip -r requirements.txt```

   Then open a python shell and run the following commands:
   ```
   import nltk
   nltk.download("wordnet")
   nltk.download("punkt")
   nltk.download("stopwords")
   ```
1. Follow the instructions in the [static folder](static/models/README.md) to get embedding model and vectors.
1. Set up the database.
    ```console
    (venv) foo@bar$ flask db init
    (venv) foo@bar$ flask db migrate -m "initial version of the database"
    (venv) foo@bar$ flask db upgrade
    ```
   **Note:** If you want to recreate the database during development, delete the app.db file and the migrations directory, and run the commands above.
1. Insert static data to the database. More instructions will follow with examples of supported data formats.
1. You can now run the application.
    ```console
   (venv) foo@bar$ flask run
    ```
   **Note:** You may also be able to run the application directly from your IDE. For example, for PyCharm, you can do so by creating a flask run configuration.

### Useful utilities for development
1. You can create a flask shell to debug parts of the code without having to launch the web application. Control what you expose to the shell in the [axies.py](axies.py) file. To launch the shell run:
    ```console
   (venv) foo@bar$ flask shell
    ```
    **Note:** Make sure you have the shell variable `FLASK_APP` set to `axies.py` in order to access axies-specific objects. If you want to dynamically relaod flask upon making changes, also set the `FLASK_ENV` to `development`.
