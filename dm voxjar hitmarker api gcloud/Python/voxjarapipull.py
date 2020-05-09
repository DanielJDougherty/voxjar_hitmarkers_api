import voxjar
import json
import time
from dateutil.parser import parse
from datetime import datetime, timedelta
import re


# Version Control = 5.8.2020, this is set to run 24 catagories to export 1 day, 2 days back from today. 

# TODO: add retry logic for each request

def login(email, password, client, retry_count):
    document = """
      mutation($email:String!, $password:String!) {
        login(email:$email, password:$password)
      }
    """
    creds = {"email": email, "password": password}
    try:
      response = client.execute(document, variable_values=creds)
      return response.get("login")
    except Exception as e:
      print('failed to login: {}'.format(e))
      if retry_count<3:
        retry_count+=1
        print('pausing 2 secs')
        time.sleep(2)
        print('retrying')
        response = login(email, password, client, retry_count)
        return response
      else:
        return False
      

   

def get_transcript(call_id, token, client, retry_count):
  # print('getting transcript')
  document="""query($filter:CallFilterInput) {
      calls(filter: $filter) {
        transcript{
          text
          timestamp
          confidence
          length
        }
      }
    }"""
  filters={"filter": {
            "identifier": {
              "equalTo": call_id
            }
          }
        }
  try:
    response = client.execute(document, variable_values=filters)
    return response.get("calls",[])[0].get('transcript')
  except Exception as e:
      print('failed to get transcript: {}'.format(e))
      if retry_count<3:
        retry_count+=1
        print('pausing 2 secs')
        time.sleep(2)
        print('retrying')
        response = get_transcript(call_id, token, client, retry_count)
        return response
      else:
        return False
  # print('transcript')

def get_agent_metadata(ident, token, client, retry_count):
  # print('getting agent metadata')
  document="""query($filter: UserFilterInput){
    users(filter: $filter){
      metadata
    }
  }
  """
  filters={'filter':{
      "identifier":{
        "equalTo":ident
      }
    }
  }
  try:
    response = client.execute(document, variable_values=filters)
    return response.get('users',[])[0].get('metadata', None)
  except Exception as e:
      print('failed to get user data: {}'.format(e))
      if retry_count<3:
        retry_count+=1
        print('pausing 2 secs')
        time.sleep(2)
        print('retrying')
        response = get_agent_metadata(ident, token, client, retry_count)
        return response
      else:
        return False

def get_search_results(filters, token, client, retry_count):
    # print('getting search results')
    document = """query($filter: CallFilterInput, $query: SearchQueryInput!){
        search(filter: $filter, query:$query){
          count{
            successful
            unsuccessful
          }
          calls{
            successful{
              identifier
              timestamp
              tags
              duration
              silenceDuration
              direction
              metadata
              type{
                id
              }
              disposition{
                id
              }
              participants{
                agents{
                  name
                  identifier
                }
                customers{
                  name
                  identifier
                }
              }
              
            }
            unsuccessful{
              identifier
              timestamp
              tags
              duration
              silenceDuration
              direction
              metadata
              type{
                id
              }
              disposition{
                id
              }
              participants{
                agents{
                  name
                  identifier
                }
                customers{
                  name
                  identifier
                }
              }
              
            }
          }
        }
      }"""
    try:
      response = client.execute(document, token=token, variable_values=filters)
      return response.get('search', [])
    except Exception as e:
      print('failed to get call data: {}'.format(e))
      if retry_count<3:
        retry_count+=1
        print('pausing 2 secs')
        time.sleep(2)
        print('retrying')
        response = get_search_results(filters, token, client, retry_count)
        return response
      else:
        print(e)
        return False

def get_saved_searches(filters, token, client, retry_count):
    # print("getting saved searches")
    document = """query($filter: SavedCallFilterFilterInput){
        callFilters(filter: $filter){
          name
          filter
        }
      }"""
    try:
      response = client.execute(document, token=token, variable_values=filters)
      return response.get('callFilters', [])
    except Exception as e:
      print('failed to get saved searches: {}'.format(e))
      if retry_count<3:
        retry_count+=1
        print('pausing 2 secs')
        time.sleep(2)
        print('retrying')
        response = get_saved_searches(filters, token, client, retry_count)
        return response
      else:
        return False


def get_dispositions(token, client, retry_count):
  # print('getting dispositions')
  document = """query{
      dispositions{
        name
        id
      }
    }"""
  try:
    response = client.execute(document, token=token)
    return response.get('dispositions',[])
  except Exception as e:
      print('failed to get disposition list: {}'.format(e))
      if retry_count<3:
        retry_count+=1
        print('pausing 2 secs')
        time.sleep(2)
        print('retrying')
        response = get_dispositions(token, client, retry_count)
        return response
      else:
        return False

def match_list_items(match, list):
  # print(match)
  for item in list:
    # print(item.get('id'))
    if item.get('id') == match:
      return item.get('name')
  # return None


def get_types(token, client, retry_count):
  # print('getting call types')
  document = """query{
      callTypes{
        name
        id
      }
    }"""
  try:
    response = client.execute(document, token=token)
    return response.get('callTypes',[])
  except Exception as e:
      print('failed to get call type list: {}'.format(e))
      if retry_count<3:
        retry_count+=1
        print('pausing 2 secs')
        time.sleep(2)
        print('retrying')
        response = get_types(token, client, retry_count)
        return response
      else:
        return False

def convert_duration(duration_dict):
  # print(duration_dict)
  secs=0
  secs+= duration_dict.get('hours',0)*3600
  secs+= duration_dict.get('minutes',0)*60
  secs+= duration_dict.get('seconds',0)
  secs+= duration_dict.get('milliseconds',0)*.001
  # print(secs)
  return secs


def list_to_dict(list):
  return_obj={}
  for item in list:
    return_obj[item]=0
  # print(return_obj)
  return return_obj

def build_call_dict(call, agent_data, transcript, dispositions, call_types, search_responses, searches_outcomes, search_name, match, first_search, search_list):
  call_id=call.get('identifier')
  # print('building call dictionary')
  
  if first_search:
    search_matches={}
    for search in search_list:
      search_matches[search.replace(' ', '_').replace('-', '_')]=0

    
    search_matches[search_name.replace(' ', '_').replace('-', '_')]=match
    
    timestamp = parse(call.get('timestamp', None))
    timestamp-=timedelta(hours=6)
    timestamp=timestamp.isoformat()

    disposition=match_list_items(call.get('disposition', {}).get('id', None), dispositions)
    call_type=match_list_items(call.get('type', {}).get('id', None), call_types)

    duration=convert_duration(call.get('duration', None))
    silence= convert_duration(call.get('silenceDuration', None))
    
    metadata={
      **agent_data,
      "timestamp":timestamp,
      "id":call_id,
      "transcript":transcript,
      "tags":call.get('tags', None),
      "duration":duration,
      "silenceDuration":silence,
      "direction":call.get('direction', None),
      **call.get('metadata', None),
      "type":call_type,
      "disposition": disposition,
      "agentId":call.get('participants', {}).get('agents', {})[0].get('identifier', None),
      "agentName":call.get('participants', {}).get('agents', {})[0].get('name', None),
      "customerId":call.get('participants', {}).get('customers', {})[0].get('identifier', None),
      "customerName":call.get('participants', {}).get('customers', {})[0].get('name', None),
      **search_matches
    }
    # print(json.dumps(call, indent=2))
    # print('appending to file')
    # with open('results.json', 'a') as f:
    #   f.write(json.dumps(call, indent=2))
      # f.write(',')
    # TODO: write results to a db as they complete
    call ={}
    # print(metadata)
    for key in metadata:
      # print(key)
      new_key= key.replace(' ', '_').replace('-', '_')
      # print(new_key)
      call[new_key] = metadata.get(key)
    # print(call)

  else:
    if search_responses.get(call_id, False):
      call = search_responses[call_id]
      call[search_name.replace(' ', '_').replace('-', '_')]= match
      # for key in call:
      #   print(key)
      #   new_key= key.replace(' ', '_').replace('-', '_')
      #   print(new_key)
      #   call[new_key] = call.pop(key)
      # # print(call)

  return call_id, call

def build_search_dict(searches, login_token, client, search_responses, searches_outcomes, search_list):
  first_search=True
  for search in searches:
    # print(first_search)
    if search.get('name',{}) in search_list:
      # print('building dictionary with search: {}'.format(search.get('name')))
      search_name=search.get('name')



      filters=dict(search.get('filter'))
      # print(filters.get('transcript'))


      # Change this to match whatever you want - overrides on all search queries
      #less than or equal to is from today, so the second must be larger than the first one (6days from May 4 be with you )
      filters['timestamp']={'lessThanOrEqualTo': {'subtract': {'day': 2}, 'atStartOf': 'd'}, 'greaterThanOrEqualTo': {'subtract': {'day': 3}, 'atStartOf': 'd'}}

      
      print(filters)
      if filters.get('transcript'):
        del filters['transcript']
      advanced=re.sub("\s+", "<->", search.get('filter', {}).get('transcript',{}).get('matches', ""))
      # advanced=search.get('filter', {}).get('transcript',{}).get('matches', "").replace(" ", "<->")
      # print(advanced)



      query={
        "query":{
          "advanced":advanced, 
          "options":{
            "selection":{
              "start":"<span style=\"background-color: #4FC3F7; color: #fff; padding: 0 4px; border-radius: 2px;\">","end":"</span>"
            }
          }
        },
        "filter":filters,
      }

      # print(query)

      response=get_search_results(query, login_token, client, 0)
      # json.loads(response)
      # print(json.dumps(response.get('count'), indent=2))

      call_types=get_types(login_token, client, 0)
      dispositions=get_dispositions(login_token, client, 0)


      successful=response.get('calls',{}).get('successful')
      unsuccessful=response.get('calls',{}).get('unsuccessful')

      for call in successful:            
        #transcript =get_transcript(call.get('identifier'), login_token, client, 0)
        transcript=''
        agent_data=get_agent_metadata(call.get('participants', {}).get('agents', {})[0].get('identifier') , login_token, client, 0)
        # print(agent_data)
        # print(transcript)
        call_id, call_dict =build_call_dict(call, agent_data, transcript, dispositions, call_types, search_responses, searches_outcomes, search_name, 1, first_search, search_list)
        search_responses[call_id]=call_dict
      if first_search:
        for call in unsuccessful:
          transcript=''
          agent_data=get_agent_metadata(call.get('participants', {}).get('agents', {})[0].get('identifier') , login_token, client, 0)
          call_id, call_dict =build_call_dict(call, agent_data, transcript, dispositions, call_types, search_responses, searches_outcomes, search_name, 0, first_search, search_list)
          search_responses[call_id]=call_dict
      first_search=False

def run(login_token, client, search_list):
  search_responses={}
  searches_outcomes=list_to_dict(search_list)
  # print(searches_outcomes)

  search_filter={
        "filter": {
            "status": {
              "equalTo": "ACTIVE"
            }
          }
        }

  saved_searches=get_saved_searches(search_filter, login_token, client, 0)
  build_search_dict(saved_searches, login_token, client, search_responses, searches_outcomes, search_list)
  return search_responses
 


def main():
  # TODO: date filter, connect to database
  client = voxjar.Client(url='https://api.voxjar.com:9000')

  # Your credentials
  email="david@voxjar.com"
  password="sQmMbW8ZeXAZRcx"

  login_token = login(email, password, client, 0)
  

  # Add search names here
  search_list=[
    # WORKING SEARCHES
    "exp7forbidden", 
    "exp7coronavirus",
    "exp7deceased",
    "exp7prescriptions",
    "exp7travelto",
    "exp7howfar",
    "exp7hospitalized",
    "exp7medicare",
    "exp7notinterested",
    "exp7pcphysician",
    "exp7afterhours",
    #"exp7verbalcontract",
    "exp7whatsimportant",
    "exp7opening",
    "exp7reachedvoicemail",
    "exp7trial",
    "exp7secondopinion",
    "exp7nocost",
    "exp7itsfree",
    "exp7secureline",
    "exp7timeofday",
    "exp7dateofbirth",
    "exp7appointmenttype",
    "exp7appointavailable",
  ]
   
  response =run(login_token, client, search_list)
  r = json.dumps(response)
  json_obj= json.loads(r)


  
  with open('trasnformme.json', 'w') as f:
      for record in json_obj:
        f.write(json.dumps(json_obj[record]).replace('\n',' ')+'\n')

  
  
if __name__ == "__main__":
    main()

 