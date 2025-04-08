from django.http import JsonResponse

from .error_messages import ErrorMessage


class ApiResponse(JsonResponse):
    """
    This class creates a standard API response in the format of a JsonResponse.
    It takes in data, a message, an error, and a status code, and returns a JsonResponse object with the following format:
    {
        'message': 'success' or error message,
        'data': json data,
        'error': error message (if there is an error)
    }
    Author: Ras Dwivedi
    Email: rasd.phd@gmail.com
    Created: Jan 16,2023
    """

    def __init__(self, data=None, msg="success", err=None, status=None, exp=None, **kwargs):
        if exp:
            # case when there is an user or server exception
            response_data = {
                "success": False,
                "data": data if data else {},
                "error": str(exp)
            }
            try:
                status = exp.status
            except Exception as e:
                status = 400
        elif err:
            # if not isinstance(err,ErrorMessage):
            #     raise Exception("Error message should be enum only")
            # try:
            #     err_message = err.name
            # except Exception as e:
            #     raise e
            # The case when there was error, and user forgets to set the message as error
            if not isinstance(err,ErrorMessage):
                err_message = err
            else:
                err_message = err.name
            if msg == "success":
                response_data = {
                    "success": False,
                    "data": data if data else {},
                    "error": err_message
                }
            # identical case, just for forward compatibility
            elif msg:
                response_data = {
                    "success": False,
                    "data": data if data else {},
                    "error": err_message
                }
            else:
                response_data = {
                    "success": False,
                    "data": data if data else {},
                    "error": err_message
                }
            if not status:
                status = 400  # default status in case of error
        else:
            response_data = {
                "success": True if (msg == "success" or msg == True) else False,
                "data": data if data else {},
            }
            if not status:
                status = 200  # default status in case of success
        super().__init__(response_data, status=status, **kwargs)


class ApiSuccessResponse(JsonResponse):
    def __init__(self, **kwargs):
        """
        class for default success response
        """
        response_data = {
            "success": True,
            "data": {}
        }
        super().__init__(response_data, status=200, **kwargs)