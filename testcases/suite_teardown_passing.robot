*** Settings ***
Suite Teardown    Do Suite Teardown

*** Test Cases ***
Test Case 1
    Log    In Test Case 1

Test Case 2
    Log    In Test Case 2


*** Keywords ***
Do Suite Teardown
    Sleep   1s
    Log     Doing suite teardown
    Keyword That Warns

Keyword That Warns
    Log     This keyword warns    level=WARN
