*** Settings ***
Suite Setup    Do Suite Setup

*** Test Cases ***
Test Case 1
    Log    In Test Case 1

Test Case 2
    Log    In Test Case 2


*** Keywords ***
Do Suite Setup
    Sleep   1s
    Log     Doing suite setup
    Keyword That Warns

Keyword That Warns
    Log     This keyword warns    level=WARN
