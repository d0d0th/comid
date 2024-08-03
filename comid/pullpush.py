import requests

class PullPushApi:
    api_submssion_url = "https://api.pullpush.io/reddit/search/submission/?"

    def search_submissions(self, **kwargs):
        """
        Method for searching submissions, returns an array of submissions
        Input:
           kewargs - Query parameters for searching submissions
        Output:
            Response generator object
        """
        query = ""
        for (k, v) in kwargs.items():
            if query:
                query+="&"
            query+=str(k)+"="+str(v)
        api_url = self.api_submssion_url+query
        response = requests.get(api_url)
        return response.json()['data']


