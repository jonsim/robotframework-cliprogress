*** Settings ***
Library    Collections
Library    OperatingSystem
Library    Process
Library    String

*** Variables ***
${DELAY_SHORT}    0.5s
${DELAY_MEDIUM}   1s
${DELAY_LONG}     2s
${TEST_MESSAGE}   Hello, Robot Framework!

*** Test Cases ***
Test Case 1 - Fast
    Log    Starting Test Case 1
    ${result}=    Evaluate    2 + 2
    Should Be Equal As Numbers    ${result}    4
    Log    Test Case 1 completed.

Test Case 2 - Medium
    Log    Starting Test Case 2
    Sleep    ${DELAY_SHORT}
    ${files}=    List Files In Directory    ${CURDIR}
    Log    Found files: ${files}
    Log    Test Case 2 completed.

Test Case 3 - Slow
    Log    Starting Test Case 3
    Sleep    ${DELAY_LONG}
    ${text}=    Get Substring    ${TEST_MESSAGE}    0    5
    Should Be Equal    ${text}    Hello
    Log    Test Case 3 completed.

Test Case 4 - Run Process
    Log    Starting Test Case 4
    ${output}=    Run Process    echo    ${TEST_MESSAGE}
    Should Contain    ${output.stdout}    Robot Framework
    Log    Test Case 4 completed.

Test Case 5 - Fast
    Log    Starting Test Case 5
    ${list}=    Create List    1    2
    Append To List    ${list}    4
    Length Should Be    ${list}    4
    Log    Test Case 5 completed.

Test Case 6 - Medium
    Log    Starting Test Case 6
    Sleep    ${DELAY_MEDIUM}
    ${env_var}=    Get Environment Variable    PATH
    Should Not Be Empty    ${env_var}
    Log    Test Case 6 completed.

Test Case 7 - Fast
    Log    Starting Test Case 7
    ${string}=    Replace String    Robot Framework    Framework    Listener
    Should Be Equal    ${string}    Robot Listener
    Log    Test Case 7 completed.

Test Case 8 - Fast
    Log    Starting Test Case 8
    ${number}=    Evaluate    10 * 10
    Should Be Equal As Numbers    ${number}    100
    Log    Test Case 8 completed.
