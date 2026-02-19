*** Settings ***
Library    Collections
Library    OperatingSystem
Library    Process
Library    String

*** Variables ***
${DELAY_SHORT}    0.3s
${DELAY_MEDIUM}   0.8s
${DELAY_LONG}     3s
${GREETING}       Welcome to Robot Framework!

*** Test Cases ***
Test Case 1 - Fast
    Log    Starting Test Case 1
    ${value}=    Evaluate    5 + 3
    Should Be Equal As Numbers    ${value}    8
    Log    Test Case 1 completed.

Test Case 2 - Medium
    Log    Starting Test Case 2
    Sleep    ${DELAY_MEDIUM}
    ${files}=    List Files In Directory    ${CURDIR}
    Log    Files in directory: ${files}
    Log    Test Case 2 completed.

Test Case 3 - Slow
    Log    Starting Test Case 3
    Sleep    ${DELAY_LONG}
    ${substring}=    Get Substring    ${GREETING}    0    7
    Should Be Equal    ${substring}    Welcum
    Log    Test Case 3 completed.

Test Case 4 - Run Process
    Log    Starting Test Case 4
    ${output}=    Run Process    ls    -l
    Should Contain    ${output.stdout}    total
    Log    Test Case 4 completed.

Test Case 5 - Fast
    Log    Starting Test Case 5
    ${list}=    Create List    A    B    C
    Append To List    ${list}    D
    Length Should Be    ${list}    4
    Log    Test Case 5 completed.

Test Case 6 - Medium
    Log    Starting Test Case 6
    Sleep    ${DELAY_MEDIUM}
    ${env_var}=    Get Environment Variable    HOME
    Should Not Be Empty    ${env_var}
    Log    Test Case 6 completed.

Test Case 7 - Fast
    Log    Starting Test Case 7
    ${string}=    Replace String    Listener Test    Test    Suite
    Should Be Equal    ${string}    Listener Suite
    Log    Test Case 7 completed.

Test Case 8 - Fast
    Log    Starting Test Case 8
    ${number}=    Evaluate    20 / 4
    Should Be Equal As Numbers    ${number}    5
    Log    Test Case 8 completed.
