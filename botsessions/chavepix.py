import mercadopago
import asyncio
from verificar import get_credenciais

APIMERCADO = get_credenciais()['mercadopago_api']
credentials = {'access_token' : APIMERCADO  }


def get_payment(price, description):
    sdk = mercadopago.SDK(APIMERCADO)
    payment_data = {
        "transaction_amount": float(price),
        "description": str(description),
        "payment_method_id": "pix",
        "payer": {
            "email": "thayanello@hotmail.com",
            "first_name": "Leticia",
            "last_name": "Lopes",
            "identification": {
                "type": "CPF",
                "number": "36473976876"
            },
            "address": {
                "zip_code": "12576-624",
                "street_name": "Rua Itabaiana",
                "street_number": "1",
                "neighborhood": "Itaguaçu",
                "city": "Aparecida",
                "federal_unit": "SP"
            }
        }
    }
    
    payment_response = sdk.payment().create(payment_data)
    if payment_response['status'] == 201:
        payment = payment_response["response"]
        data = payment['point_of_interaction']['transaction_data']
        return [str(data['qr_code']),str(payment['id'])]
    else:
        return None, payment_response['response']['message']


async def verify_payment(payment_id):
    sdk = mercadopago.SDK(APIMERCADO)
    await asyncio.sleep(15)
    payment_response = await asyncio.to_thread(sdk.payment().get, int(payment_id))
    payment = payment_response["response"]
    if payment['status'] == "approved" and payment['status_detail'] == "accredited":
        return True
    else:
        return await verify_payment(payment_id)
        
