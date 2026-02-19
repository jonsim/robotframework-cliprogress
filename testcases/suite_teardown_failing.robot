*** Settings ***
Suite Teardown    Do Suite Teardown

*** Test Cases ***
Test Case 1
    Log    In Test Case 1

Test Case 2
    Log    In Test Case 2
    Fail    This keyword fails


*** Keywords ***
Do Suite Teardown
    Sleep   1s
    Log     Doing suite teardown
    Keyword That Fails

Keyword That Fails
    Fail    This keyword fails
