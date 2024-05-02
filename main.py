import uuid  
from phonepe.sdk.pg.payments.v1.models.request.pg_pay_request import PgPayRequest
from phonepe.sdk.pg.payments.v1.payment_client import PhonePePaymentClient
from phonepe.sdk.pg.env import Env
import base64
import pymongo
import os

# import flask
from flask import Flask, request, jsonify


app = Flask(__name__)
CONNECTION_STRING = os.getenv("CONNECTION_STRING")
# connect to the database
client = pymongo.MongoClient(CONNECTION_STRING)
# connect to payment collection
db = client["Surfila"]
collection = db["payment"]

# get environment variables
merchant_id = os.getenv("MERCHANT_ID")



salt_key = os.getenv("SALT_KEY")
salt_index = 1 # Updated with your Salt Index  
env = Env.PROD  
should_publish_events = True  
phonepe_client = PhonePePaymentClient(merchant_id, salt_key, salt_index, env, should_publish_events)

@app.route('/paynow', methods=['GET'])
def paynow():
    # get amount from params
    amount = request.args.get('amount')
    if amount is None:
        amount = 100  # 1 rupee, 100 paise  
    else:
        amount = int(amount) * 100  # converting to paise


    # base_url = os.getenv("BASE_URL")

    unique_transcation_id = str(uuid.uuid4())[:-2]
    ui_redirect_url = "https://utr-pay.susanoox.in/redirect"
    s2s_callback_url = "https://utr-pay.susanoox.in/callback"
    id_assigned_to_user_by_merchant = "utr_id_1234"  
    pay_page_request = PgPayRequest.pay_page_pay_request_builder(merchant_transaction_id=unique_transcation_id,  
                                                                 amount=amount,  
                                                                 merchant_user_id=id_assigned_to_user_by_merchant,  
                                                                 callback_url=s2s_callback_url,  
                                                                 redirect_url=ui_redirect_url)  
    pay_page_response = phonepe_client.pay(pay_page_request)  
    pay_page_url = pay_page_response.data.instrument_response.redirect_info.url

    return jsonify({"pay_page_url": pay_page_url, "amount": amount, "unique_transcation_id": unique_transcation_id})


@app.route('/callback', methods=['POST'])
def callback():
    # get the x_verify header
    x_verify = request.headers.get('x-verify')
    # get the response body
    requestString = request.data.decode('utf-8')

    json_data = request.get_json()

    # verify the response
    is_valid = phonepe_client.verify_response(x_verify=x_verify, response=requestString)
    if is_valid:
        # your logic here
        print("The response is valid")
        response = json_data['response'].encode('utf-8')
        # base64 decode the response
        print("response: ",response)
        decoded_response = base64.b64decode(response)
        print("decoded_response: ",decoded_response)
        # insert the response to the database
        collection.insert_one({"response": decoded_response.decode('utf-8')})
        return jsonify({"message": "The response is valid"})
    else:
        # your logic here
        print("The response is not valid")
        return jsonify({"message": "The response is not valid"})
    
@app.route('/redirect', methods=['GET'])
def redirect():
    payments = list(collection.find())
    for payment in payments:
        payment['_id'] = str(payment['_id'])

    # create a html table to display the payments
    heading = "<h1>Payments</h1><br>"
    table = "<table border='1'>"
    table += "<tr><th>Id</th><th>Response</th></tr>"
    for payment in payments:
        table += "<tr><td>"+payment["_id"]+"</td><td>"+payment["response"]+"</td></tr>"
    table += "</table>"
    
    return heading + table

@app.route('/get_all_payments', methods=['GET'])
def get_all_payments():
    payments = list(collection.find())
    for payment in payments:
        payment['_id'] = str(payment['_id'])
    return jsonify(payments)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4000, debug=True)
