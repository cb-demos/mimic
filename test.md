# Testing out some Unify endpoints

## Creating a component

```shell
export TOKEN="<my PAT>"
curl 'https://api.cloudbees.io/v1/organizations/5c637db2-e596-44c7-80c8-079136685917/services' \
  -H 'accept: */*' \
  -H 'authorization: Bearer <my PAT>' \
  --data-raw '{
  "service": {
    "name": "ld-hackers-org10",
    "description": "",
    "endpointId": "9a3942be-0e86-415e-94c5-52512be1138d",
    "repositoryUrl": "https://github.com/ldorg/ld-hackers-org10.git"
  }
}'
```

## Returns
```json
{"service":{"id":"ce7d4eeb-5275-4940-80f3-87c096ca438c", "name":"ld-hackers-org10", "description":"", "endpointId":"9a3942be-0e86-415e-94c5-52512be1138d", "repositoryUrl":"https://github.com/ldorg/ld-hackers-org10.git", "defaultBranch":"main", "organizationId":"5c637db2-e596-44c7-80c8-079136685917", "serviceType":"COMPONENT", "linkedComponentIds":[], "linkedEnvironmentIds":[], "repositoryHref":"https://github.com/ldorg/ld-hackers-org10"}}
```


## Creating an application

```shell
curl 'https://api.cloudbees.io/v1/organizations/5c637db2-e596-44c7-80c8-079136685917/services' \
  -H 'accept: */*' \
  -H 'authorization: Bearer <my PAT>' \
  --data-raw '{
  "service": {
    "name": "anotherone",
    "description": "",
    "repositoryUrl": "",
    "endpointId": "",
    "defaultBranch": "",
    "linkedComponentIds": [],
    "linkedEnvironmentIds": [],
    "components": [],
    "environments": [],
    "organizationId": "5c637db2-e596-44c7-80c8-079136685917",
    "serviceType": "APPLICATION"
  }
}'
```

Returns:

```json
{
  "service": {
    "id": "15459b02-cc4c-417a-8bb3-773f3f1e6b79",
    "name": "anotherone",
    "description": "",
    "endpointId": "",
    "repositoryUrl": "",
    "defaultBranch": "",
    "organizationId": "5c637db2-e596-44c7-80c8-079136685917",
    "serviceType": "APPLICATION",
    "linkedComponentIds": [],
    "linkedEnvironmentIds": [],
    "repositoryHref": ""
  }
}
```

### Add environments and components

```shell
curl 'https://api.cloudbees.io/v1/organizations/5c637db2-e596-44c7-80c8-079136685917/services/15459b02-cc4c-417a-8bb3-773f3f1e6b79' \
  -X 'PUT' \
  -H 'accept: */*' \
  -H 'authorization: Bearer <my PAT>' \
  --data-raw '{
  "service": {
    "name": "anotherone",
    "description": "",
    "linkedEnvironmentIds": ["a4a56600-19ed-43d1-aa60-cbed141c8b2a"],
    "linkedComponentIds": ["ce7d4eeb-5275-4940-80f3-87c096ca438c"],
    "serviceType": "APPLICATION",
    "organizationId": "5c637db2-e596-44c7-80c8-079136685917",
    "repositoryHref": "https://github.com/ldorg/app-0test",
    "repositoryUrl": "https://github.com/ldorg/app-0test.git",
    "defaultBranch": "main",
    "endpointId": "9a3942be-0e86-415e-94c5-52512be1138d"
  }
}'
```

Returns
```json
{
  "service": {
    "id": "15459b02-cc4c-417a-8bb3-773f3f1e6b79",
    "name": "anotherone",
    "description": "",
    "endpointId": "9a3942be-0e86-415e-94c5-52512be1138d",
    "repositoryUrl": "https://github.com/ldorg/app-0test.git",
    "defaultBranch": "main",
    "organizationId": "5c637db2-e596-44c7-80c8-079136685917",
    "serviceType": "APPLICATION",
    "linkedComponentIds": [
      "ce7d4eeb-5275-4940-80f3-87c096ca438c"
    ],
    "linkedEnvironmentIds": [
      "a4a56600-19ed-43d1-aa60-cbed141c8b2a"
    ],
    "repositoryHref": "https://github.com/ldorg/app-0test"
  }
}
```


## Create environment

```shell
curl 'https://api.cloudbees.io/v1/resources/5c637db2-e596-44c7-80c8-079136685917/endpoints' \
  -H 'accept: */*' \
  -H 'authorization: Bearer <my PAT>' \
  --data-raw '{
  "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
  "contributionId": "cb.configuration.basic-environment",
  "contributionType": "cb.platform.environment",
  "contributionTargets": [
    "cb.configuration.environments"
  ],
  "name": "myenv",
  "description": "",
  "properties": [
    {
      "name": "approvers",
      "bool": false,
      "isSecret": false
    },
    {
      "name": "FM_TOKEN",
      "string": "test",
      "isSecret": false
    },
    {
      "name": "ANOTHER",
      "string": "test",
      "isSecret": true
    }
  ]
}
'
```

Returns:
```json
{"id":"54ae03bc-491a-4b2e-897a-476d7c9d9bf7"}
```

### Update env w/ vars

```shell
curl 'https://api.cloudbees.io/v1/resources/5c637db2-e596-44c7-80c8-079136685917/endpoints/54ae03bc-491a-4b2e-897a-476d7c9d9bf7' \
  -X 'PUT' \
  -H 'accept: */*' \
  -H 'authorization: Bearer <my PAT>' \
  --data-raw '{
  "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
  "contributionId": "cb.configuration.basic-environment",
  "contributionType": "cb.platform.environment",
  "contributionTargets": [
    "cb.configuration.environments"
  ],
  "name": "myenv",
  "description": "",
  "properties": [
    {
      "name": "approvers",
      "bool": false,
      "isSecret": false
    },
    {
      "name": "FM_TOKEN",
      "string": "Hello",
      "isSecret": false
    },
    {
      "name": "ANOTHER",
      "string": "*****",
      "isSecret": true
    }
  ]
}
'
```

```shell
curl 'https://api.cloudbees.io/v1/resources/5c637db2-e596-44c7-80c8-079136685917/endpoints?filter.contributionTypes=cb.platform.environment&parents=true&pagination.pageLength=1000' \
  -H 'accept: */*' \
  -H 'accept-language: en-US,en;q=0.9' \
  -H 'authorization: Bearer <my PAT>'
```

returns:

```json
{
  "endpoints": [
    {
      "id": "bfba72bd-ec09-4071-819b-11d1453372bb",
      "parentId": "",
      "resourceId": "92b02544-e6e4-11ea-981f-42010a83ae1a",
      "name": "fm-analytics",
      "audit": {
        "who": "e54d93e6-b43c-11ec-a57b-42010a83ae5a",
        "when": "2024-05-23T18:17:01.509347435Z",
        "why": "ENDPOINT:CREATE"
      },
      "contributionType": "cb.platform.environment",
      "contributionTargets": [
        "cb.configuration.environments"
      ],
      "contributionId": "cb.configuration.basic-environment",
      "properties": [
        {
          "name": "approvers",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "e54d93e6-b43c-11ec-a57b-42010a83ae5a",
            "when": "2024-05-23T18:17:01.509347435Z",
            "why": "ENDPOINT:CREATE"
          },
          "resourceId": "",
          "isDeleted": false,
          "isMultiline": false
        }
      ],
      "isDisabled": false,
      "description": "Environment Used to Test FM Analytics Data"
    },
    {
      "id": "da92d669-0eeb-4e2d-86c6-15d8e9d152fc",
      "parentId": "",
      "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
      "name": "ld-hackers-prod",
      "audit": {
        "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
        "when": "2025-07-22T18:48:04.822424266Z",
        "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\",\"required_permissions\":[{\"action\":3,\"type\":7}]}"
      },
      "contributionType": "cb.platform.environment",
      "contributionTargets": [
        "cb.configuration.environments"
      ],
      "contributionId": "cb.configuration.basic-environment",
      "properties": [
        {
          "name": "approvers",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
            "when": "2025-07-22T18:48:04.822424266Z",
            "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\",\"required_permissions\":[{\"action\":3,\"type\":7}]}"
          },
          "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
          "isDeleted": false,
          "isMultiline": false,
          "bool": false
        },
        {
          "name": "namespace",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
            "when": "2025-07-22T18:48:04.822424266Z",
            "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\",\"required_permissions\":[{\"action\":3,\"type\":7}]}"
          },
          "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
          "isDeleted": false,
          "isMultiline": false,
          "string": "ld-hackers-prod"
        },
        {
          "name": "FM_TOKEN",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": true,
          "audit": {
            "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
            "when": "2025-07-22T18:48:04.822424266Z",
            "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\",\"required_permissions\":[{\"action\":3,\"type\":7}]}"
          },
          "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
          "isDeleted": false,
          "isMultiline": false,
          "string": "*****"
        }
      ],
      "isDisabled": false,
      "description": ""
    },
    {
      "id": "a4a56600-19ed-43d1-aa60-cbed141c8b2a",
      "parentId": "",
      "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
      "name": "ld-hackers-qa",
      "audit": {
        "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
        "when": "2025-07-22T18:48:10.537604835Z",
        "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\",\"required_permissions\":[{\"action\":3,\"type\":7}]}"
      },
      "contributionType": "cb.platform.environment",
      "contributionTargets": [
        "cb.configuration.environments"
      ],
      "contributionId": "cb.configuration.basic-environment",
      "properties": [
        {
          "name": "approvers",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
            "when": "2025-07-22T18:48:10.537604835Z",
            "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\",\"required_permissions\":[{\"action\":3,\"type\":7}]}"
          },
          "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
          "isDeleted": false,
          "isMultiline": false,
          "bool": false
        },
        {
          "name": "namespace",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
            "when": "2025-07-22T18:48:10.537604835Z",
            "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\",\"required_permissions\":[{\"action\":3,\"type\":7}]}"
          },
          "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
          "isDeleted": false,
          "isMultiline": false,
          "string": "ld-hackers-qa"
        },
        {
          "name": "FM_TOKEN",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": true,
          "audit": {
            "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
            "when": "2025-07-22T18:48:10.537604835Z",
            "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\",\"required_permissions\":[{\"action\":3,\"type\":7}]}"
          },
          "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
          "isDeleted": false,
          "isMultiline": false,
          "string": "*****"
        }
      ],
      "isDisabled": false,
      "description": ""
    },
    {
      "id": "6afcbc72-4619-4bd2-8fdb-afdac8532feb",
      "parentId": "",
      "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
      "name": "ld-hackers-staging",
      "audit": {
        "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
        "when": "2025-07-22T18:48:15.323240301Z",
        "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\",\"required_permissions\":[{\"action\":3,\"type\":7}]}"
      },
      "contributionType": "cb.platform.environment",
      "contributionTargets": [
        "cb.configuration.environments"
      ],
      "contributionId": "cb.configuration.basic-environment",
      "properties": [
        {
          "name": "approvers",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
            "when": "2025-07-22T18:48:15.323240301Z",
            "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\",\"required_permissions\":[{\"action\":3,\"type\":7}]}"
          },
          "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
          "isDeleted": false,
          "isMultiline": false,
          "bool": false
        },
        {
          "name": "namespace",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
            "when": "2025-07-22T18:48:15.323240301Z",
            "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\",\"required_permissions\":[{\"action\":3,\"type\":7}]}"
          },
          "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
          "isDeleted": false,
          "isMultiline": false,
          "string": "ld-hackers-staging"
        },
        {
          "name": "FM_TOKEN",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": true,
          "audit": {
            "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
            "when": "2025-07-22T18:48:15.323240301Z",
            "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\",\"required_permissions\":[{\"action\":3,\"type\":7}]}"
          },
          "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
          "isDeleted": false,
          "isMultiline": false,
          "string": "*****"
        }
      ],
      "isDisabled": false,
      "description": ""
    },
    {
      "id": "101ee70b-f504-4229-ad58-92562eb09009",
      "parentId": "",
      "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
      "name": "ld-test",
      "audit": {
        "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
        "when": "2025-07-17T13:57:24.042941663Z",
        "why": "{\"full_method\":\"/api.endpoint.EndpointService/AddEndpoint\",\"required_permissions\":[{\"action\":1,\"type\":7}]}"
      },
      "contributionType": "cb.platform.environment",
      "contributionTargets": [
        "cb.configuration.environments"
      ],
      "contributionId": "cb.configuration.basic-environment",
      "properties": [
        {
          "name": "approvers",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
            "when": "2025-07-17T13:57:24.042941663Z",
            "why": "{\"full_method\":\"/api.endpoint.EndpointService/AddEndpoint\",\"required_permissions\":[{\"action\":1,\"type\":7}]}"
          },
          "resourceId": "",
          "isDeleted": false,
          "isMultiline": false,
          "bool": false
        }
      ],
      "isDisabled": false,
      "description": ""
    },
    {
      "id": "54ae03bc-491a-4b2e-897a-476d7c9d9bf7",
      "parentId": "",
      "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
      "name": "myenv",
      "audit": {
        "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
        "when": "2025-08-22T19:15:34.443886524Z",
        "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\"}"
      },
      "contributionType": "cb.platform.environment",
      "contributionTargets": [
        "cb.configuration.environments"
      ],
      "contributionId": "cb.configuration.basic-environment",
      "properties": [
        {
          "name": "approvers",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
            "when": "2025-08-22T19:15:34.443886524Z",
            "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\"}"
          },
          "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
          "isDeleted": false,
          "isMultiline": false,
          "bool": false
        },
        {
          "name": "FM_TOKEN",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
            "when": "2025-08-22T19:15:34.443886524Z",
            "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\"}"
          },
          "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
          "isDeleted": false,
          "isMultiline": false,
          "string": "Hello"
        },
        {
          "name": "ANOTHER",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": true,
          "audit": {
            "who": "cc786812-e80c-11ea-a794-42010a83ae1a",
            "when": "2025-08-22T19:15:34.443886524Z",
            "why": "{\"full_method\":\"/api.endpoint.EndpointService/UpdateEndpoint\"}"
          },
          "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
          "isDeleted": false,
          "isMultiline": false,
          "string": "*****"
        }
      ],
      "isDisabled": false,
      "description": ""
    },
    {
      "id": "807a7064-d267-463d-b90d-153f678be104",
      "parentId": "",
      "resourceId": "92b02544-e6e4-11ea-981f-42010a83ae1a",
      "name": "production",
      "audit": {
        "who": "310969a0-e7fb-11ea-a794-42010a83ae1a",
        "when": "2023-10-04T03:59:24.650057573Z",
        "why": "ENDPOINT:CREATE"
      },
      "contributionType": "cb.platform.environment",
      "contributionTargets": [
        "cb.configuration.environments"
      ],
      "contributionId": "cb.configuration.basic-environment",
      "properties": [
        {
          "name": "approvers",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "310969a0-e7fb-11ea-a794-42010a83ae1a",
            "when": "2023-10-04T03:59:24.650057573Z",
            "why": "ENDPOINT:CREATE"
          },
          "resourceId": "",
          "isDeleted": false,
          "isMultiline": false,
          "string": "on"
        }
      ],
      "isDisabled": false,
      "description": "The production environment"
    },
    {
      "id": "93a2a0f6-bf1c-433f-9bc3-6cc540306c62",
      "parentId": "",
      "resourceId": "92b02544-e6e4-11ea-981f-42010a83ae1a",
      "name": "staging",
      "audit": {
        "who": "1fd830f2-555f-11ed-a7f3-42010a83ae7c",
        "when": "2024-08-30T20:04:01.360355413Z",
        "why": "ENDPOINT:UPDATE"
      },
      "contributionType": "cb.platform.environment",
      "contributionTargets": [
        "cb.configuration.environments"
      ],
      "contributionId": "cb.configuration.basic-environment",
      "properties": [
        {
          "name": "approvers",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "1fd830f2-555f-11ed-a7f3-42010a83ae7c",
            "when": "2024-08-30T20:04:01.360355413Z",
            "why": "ENDPOINT:UPDATE"
          },
          "resourceId": "92b02544-e6e4-11ea-981f-42010a83ae1a",
          "isDeleted": false,
          "isMultiline": false,
          "bool": true
        },
        {
          "name": "p1",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": true,
          "audit": {
            "who": "1fd830f2-555f-11ed-a7f3-42010a83ae7c",
            "when": "2024-08-30T20:04:01.360355413Z",
            "why": "ENDPOINT:UPDATE"
          },
          "resourceId": "92b02544-e6e4-11ea-981f-42010a83ae1a",
          "isDeleted": false,
          "isMultiline": false,
          "string": "*****"
        },
        {
          "name": "p2",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": true,
          "audit": {
            "who": "1fd830f2-555f-11ed-a7f3-42010a83ae7c",
            "when": "2024-08-30T20:04:01.360355413Z",
            "why": "ENDPOINT:UPDATE"
          },
          "resourceId": "92b02544-e6e4-11ea-981f-42010a83ae1a",
          "isDeleted": false,
          "isMultiline": false,
          "string": "*****"
        },
        {
          "name": "p3",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": true,
          "audit": {
            "who": "1fd830f2-555f-11ed-a7f3-42010a83ae7c",
            "when": "2024-08-30T20:04:01.360355413Z",
            "why": "ENDPOINT:UPDATE"
          },
          "resourceId": "92b02544-e6e4-11ea-981f-42010a83ae1a",
          "isDeleted": false,
          "isMultiline": false,
          "string": "*****"
        },
        {
          "name": "p4",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": true,
          "audit": {
            "who": "1fd830f2-555f-11ed-a7f3-42010a83ae7c",
            "when": "2024-08-30T20:04:01.360355413Z",
            "why": "ENDPOINT:UPDATE"
          },
          "resourceId": "92b02544-e6e4-11ea-981f-42010a83ae1a",
          "isDeleted": false,
          "isMultiline": false,
          "string": "*****"
        },
        {
          "name": "aslkjfksajjj",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": true,
          "audit": {
            "who": "1fd830f2-555f-11ed-a7f3-42010a83ae7c",
            "when": "2024-03-19T19:10:43.352624820Z",
            "why": "ENDPOINT:UPDATE"
          },
          "resourceId": "92b02544-e6e4-11ea-981f-42010a83ae1a",
          "isDeleted": false,
          "isMultiline": false,
          "string": "*****"
        }
      ],
      "isDisabled": false,
      "description": "The staging environment"
    },
    {
      "id": "46ae52cc-e7e1-4bd5-9852-7fad3c744840",
      "parentId": "",
      "resourceId": "92b02544-e6e4-11ea-981f-42010a83ae1a",
      "name": "test",
      "audit": {
        "who": "4b9e80a2-6c8d-11ed-9d5a-42010a83ae7c",
        "when": "2024-09-10T07:49:53.567583978Z",
        "why": "ENDPOINT:UPDATE"
      },
      "contributionType": "cb.platform.environment",
      "contributionTargets": [
        "cb.configuration.environments"
      ],
      "contributionId": "cb.configuration.basic-environment",
      "properties": [
        {
          "name": "approvers",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "4b9e80a2-6c8d-11ed-9d5a-42010a83ae7c",
            "when": "2024-09-10T07:49:53.567583978Z",
            "why": "ENDPOINT:UPDATE"
          },
          "resourceId": "",
          "isDeleted": false,
          "isMultiline": false
        },
        {
          "name": "k1",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "4b9e80a2-6c8d-11ed-9d5a-42010a83ae7c",
            "when": "2024-09-10T07:49:53.567583978Z",
            "why": "ENDPOINT:UPDATE"
          },
          "resourceId": "",
          "isDeleted": false,
          "isMultiline": false,
          "string": "v1"
        }
      ],
      "isDisabled": false,
      "description": "test"
    },
    {
      "id": "14943d97-e81a-46bc-8319-5068ec0ccd30",
      "parentId": "",
      "resourceId": "92b02544-e6e4-11ea-981f-42010a83ae1a",
      "name": "test-fai;",
      "audit": {
        "who": "UNKNOWN",
        "when": "2025-05-22T09:56:32.853776369Z",
        "why": "{\"full_method\":\"/api.endpoint.EndpointService/AddEndpoint\"}"
      },
      "contributionType": "cb.platform.environment",
      "contributionTargets": [
        "cb.configuration.environments"
      ],
      "contributionId": "cb.configuration.basic-environment",
      "properties": [
        {
          "name": "approvers",
          "description": "",
          "exportName": "",
          "isProtected": false,
          "isSecret": false,
          "audit": {
            "who": "UNKNOWN",
            "when": "2025-05-22T09:56:32.853776369Z",
            "why": "{\"full_method\":\"/api.endpoint.EndpointService/AddEndpoint\"}"
          },
          "resourceId": "",
          "isDeleted": false,
          "isMultiline": false
        }
      ],
      "isDisabled": false,
      "description": ""
    }
  ],
  "pagination": {
    "page": 1,
    "pageLength": 1000,
    "sort": {
      "fieldName": "name",
      "order": "ASCENDING"
    },
    "lastPage": true
  }
}
```


## Create flag

```shell
curl 'https://api.cloudbees.io/v1/applications/5c637db2-e596-44c7-80c8-079136685917/flags' \
  -H 'accept: */*' \
  -H 'accept-language: en-US,en;q=0.9' \
  -H 'authorization: Bearer <my PAT>' \
  --data-raw '{
  "name": "mine2",
  "description": "",
  "flagType": "Boolean",
  "labels": [],
  "isPermanent": false,
  "variants": [
    "true",
    "false"
  ]
}'
```

returns

```json
{
  "flag": {
    "id": "7abb2d09-3eb4-4894-a6a4-20b16f6e43a6",
    "name": "mine2",
    "description": "",
    "flagType": "Boolean",
    "variants": [
      "true",
      "false"
    ],
    "resourceId": "5c637db2-e596-44c7-80c8-079136685917",
    "labels": [],
    "isPermanent": false,
    "cascUrl": ""
  }
}
```


### Enable flag

```shell
curl 'https://api.cloudbees.io/v1/applications/5c637db2-e596-44c7-80c8-079136685917/flags/7abb2d09-3eb4-4894-a6a4-20b16f6e43a6/configuration/environments/bfba72bd-ec09-4071-819b-11d1453372bb/configstate' \
  -H 'accept: */*' \
  -H 'accept-language: en-US,en;q=0.9' \
  -H 'authorization: Bearer <my PAT>' \
  --data-raw '{"enabled":true}'
```

returns

```json
{}
```

### Configure flag in environment

#### Example for targeting a group

```shell
curl 'https://api.cloudbees.io/v1/applications/5c637db2-e596-44c7-80c8-079136685917/flags/7abb2d09-3eb4-4894-a6a4-20b16f6e43a6/configuration/environments/bfba72bd-ec09-4071-819b-11d1453372bb' \
  -X 'PATCH' \
  -H 'accept: */*' \
  -H 'accept-language: en-US,en;q=0.9' \
  -H 'authorization: Bearer <my PAT>' \
  --data-raw '{
  "defaultValue": false,
  "conditions": [
    {
      "allOf": [
        {
          "anyOf": [
            {
              "group": {
                "id": "4fb8623e-5e57-4af7-ab62-aca3f13eabeb"
              }
            }
          ]
        }
      ],
      "flagValue": true
    }
  ]
}
'
```

#### Example for no conditions, just off 
```shell
curl 'https://api.cloudbees.io/v1/applications/5c637db2-e596-44c7-80c8-079136685917/flags/7abb2d09-3eb4-4894-a6a4-20b16f6e43a6/configuration/environments/a4a56600-19ed-43d1-aa60-cbed141c8b2a' \
  -X 'PATCH' \
  -H 'accept: */*' \
  -H 'accept-language: en-US,en;q=0.9' \
  -H 'authorization: Bearer <my PAT>' \
  --data-raw '{"defaultValue":false,"enabled":true,"conditions":[]}'
```

## Listing components

```shell
curl 'https://api.cloudbees.io/v1/organizations/5c637db2-e596-44c7-80c8-079136685917/services?typeFilter=COMPONENT_FILTER' \
  -H 'accept: */*' \
  -H 'authorization: Bearer <my PAT>'
```

Returns

```json
{
  "service": [
    {
      "id": "1852180d-86a6-4e16-beb0-fd3a2f7c74dd",
      "name": "hackers-auth",
      "description": "",
      "endpointId": "9a3942be-0e86-415e-94c5-52512be1138d",
      "repositoryUrl": "https://github.com/ldorg/hackers-auth.git",
      "defaultBranch": "main",
      "organizationId": "fdb4128a-6d2b-403c-aae4-8466a906318c",
      "serviceType": "COMPONENT",
      "linkedComponentIds": [],
      "linkedEnvironmentIds": [],
      "repositoryHref": ""
    },
    {
      "id": "3395a2b9-7e2c-4736-910a-0cd3fea6a2bb",
      "name": "jira-sandbox",
      "description": "",
      "endpointId": "9a3942be-0e86-415e-94c5-52512be1138d",
      "repositoryUrl": "https://github.com/ldorg/jira-sandbox.git",
      "defaultBranch": "main",
      "organizationId": "5c637db2-e596-44c7-80c8-079136685917",
      "serviceType": "COMPONENT",
      "linkedComponentIds": [],
      "linkedEnvironmentIds": [],
      "repositoryHref": ""
    },
    {
      "id": "3840c995-5935-4d98-ba76-e02dd5064fba",
      "name": "fm-sandbox",
      "description": "",
      "endpointId": "9a3942be-0e86-415e-94c5-52512be1138d",
      "repositoryUrl": "https://github.com/ldorg/fm-sandbox.git",
      "defaultBranch": "main",
      "organizationId": "5c637db2-e596-44c7-80c8-079136685917",
      "serviceType": "COMPONENT",
      "linkedComponentIds": [],
      "linkedEnvironmentIds": [],
      "repositoryHref": ""
    },
    {
      "id": "772e333c-4872-484a-aec1-b813458f684b",
      "name": "hackers-api",
      "description": "",
      "endpointId": "9a3942be-0e86-415e-94c5-52512be1138d",
      "repositoryUrl": "https://github.com/ldorg/hackers-api.git",
      "defaultBranch": "main",
      "organizationId": "fdb4128a-6d2b-403c-aae4-8466a906318c",
      "serviceType": "COMPONENT",
      "linkedComponentIds": [],
      "linkedEnvironmentIds": [],
      "repositoryHref": ""
    },
    {
      "id": "74d19da3-43fa-4c01-a032-9b9ab3d07d2b",
      "name": "hackers-web",
      "description": "",
      "endpointId": "9a3942be-0e86-415e-94c5-52512be1138d",
      "repositoryUrl": "https://github.com/ldorg/hackers-web.git",
      "defaultBranch": "main",
      "organizationId": "fdb4128a-6d2b-403c-aae4-8466a906318c",
      "serviceType": "COMPONENT",
      "linkedComponentIds": [],
      "linkedEnvironmentIds": [],
      "repositoryHref": ""
    },
    {
      "id": "051471b6-491e-4231-8f36-a712b6fbfbc6",
      "name": "blackduck-scan-demo",
      "description": "",
      "endpointId": "e8c14f62-66e8-4846-a077-3b9a887a7255",
      "repositoryUrl": "https://github.com/cloudbees-days/blackduck-scan-demo.git",
      "defaultBranch": "main",
      "organizationId": "0dcbd381-a28d-4789-a528-3472ed9aee41",
      "serviceType": "COMPONENT",
      "linkedComponentIds": [],
      "linkedEnvironmentIds": [],
      "repositoryHref": ""
    },
    {
      "id": "8d707972-a875-47db-ba86-a5f1383d9f68",
      "name": "blackduck-demo",
      "description": "",
      "endpointId": "9a3942be-0e86-415e-94c5-52512be1138d",
      "repositoryUrl": "https://github.com/ldorg/blackduck-demo.git",
      "defaultBranch": "main",
      "organizationId": "0dcbd381-a28d-4789-a528-3472ed9aee41",
      "serviceType": "COMPONENT",
      "linkedComponentIds": [],
      "linkedEnvironmentIds": [],
      "repositoryHref": ""
    }
  ]
}
```


## Listing applications

```shell
curl 'https://api.cloudbees.io/v1/organizations/5c637db2-e596-44c7-80c8-079136685917/services?typeFilter=APPLICATION_FILTER' \
  -H 'accept: */*' \
  -H 'authorization: Bearer <my PAT>'
```

Return

```json
{
  "service": [
    {
      "id": "89e5d7d6-1dde-4a84-9be6-7a75f5c82201",
      "name": "ld-test",
      "description": "",
      "endpointId": "",
      "repositoryUrl": "",
      "defaultBranch": "",
      "organizationId": "5c637db2-e596-44c7-80c8-079136685917",
      "serviceType": "APPLICATION",
      "linkedComponentIds": [],
      "linkedEnvironmentIds": [
        "101ee70b-f504-4229-ad58-92562eb09009"
      ],
      "repositoryHref": ""
    },
    {
      "id": "12f8ad56-ae08-4802-b712-b3a52ba73202",
      "name": "demo-app-1754917623231",
      "description": "Demo application created via extension",
      "endpointId": "",
      "repositoryUrl": "",
      "defaultBranch": "",
      "organizationId": "5c637db2-e596-44c7-80c8-079136685917",
      "serviceType": "APPLICATION",
      "linkedComponentIds": [],
      "linkedEnvironmentIds": [],
      "repositoryHref": ""
    },
    {
      "id": "41379f80-bf1f-4c22-931c-7ff804c84589",
      "name": "HackersApp",
      "description": "",
      "endpointId": "9a3942be-0e86-415e-94c5-52512be1138d",
      "repositoryUrl": "https://github.com/ldorg/hackers-app.git",
      "defaultBranch": "main",
      "organizationId": "5c637db2-e596-44c7-80c8-079136685917",
      "serviceType": "APPLICATION",
      "linkedComponentIds": [
        "1852180d-86a6-4e16-beb0-fd3a2f7c74dd",
        "772e333c-4872-484a-aec1-b813458f684b",
        "74d19da3-43fa-4c01-a032-9b9ab3d07d2b"
      ],
      "linkedEnvironmentIds": [
        "da92d669-0eeb-4e2d-86c6-15d8e9d152fc",
        "6afcbc72-4619-4bd2-8fdb-afdac8532feb",
        "a4a56600-19ed-43d1-aa60-cbed141c8b2a"
      ],
      "repositoryHref": ""
    },
    {
      "id": "78a0cb60-94f5-497a-8b5c-8e0448981529",
      "name": "demo-app-1755097787360",
      "description": "Demo application created via extension",
      "endpointId": "",
      "repositoryUrl": "",
      "defaultBranch": "",
      "organizationId": "0dcbd381-a28d-4789-a528-3472ed9aee41",
      "serviceType": "APPLICATION",
      "linkedComponentIds": [],
      "linkedEnvironmentIds": [],
      "repositoryHref": ""
    },
    {
      "id": "15459b02-cc4c-417a-8bb3-773f3f1e6b79",
      "name": "anotherone",
      "description": "",
      "endpointId": "9a3942be-0e86-415e-94c5-52512be1138d",
      "repositoryUrl": "https://github.com/ldorg/app-0test.git",
      "defaultBranch": "main",
      "organizationId": "5c637db2-e596-44c7-80c8-079136685917",
      "serviceType": "APPLICATION",
      "linkedComponentIds": [
        "ce7d4eeb-5275-4940-80f3-87c096ca438c"
      ],
      "linkedEnvironmentIds": [
        "a4a56600-19ed-43d1-aa60-cbed141c8b2a"
      ],
      "repositoryHref": ""
    }
  ]
}
```
