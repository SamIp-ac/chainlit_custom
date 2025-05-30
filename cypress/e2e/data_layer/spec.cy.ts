import { sep } from 'path';

import { runTestServer, submitMessage } from '../../support/testUtils';
import { ExecutionMode } from '../../support/utils';

function login() {
  cy.get("[id='email']").type('admin');
  cy.get("[id='password']").type('admin{enter}');
}

function feedback() {
  cy.location('pathname').should((loc) => {
    expect(loc).to.eq('/');
  });
  submitMessage('Hello');
  cy.location('pathname').should((loc) => {
    // starts with /thread/
    expect(loc).to.match(/^\/thread\//);
  });
  cy.get('.negative-feedback-off').should('have.length', 1);
  cy.get('.positive-feedback-off').should('have.length', 1).eq(0).click();
  cy.get('#submit-feedback').click();
  cy.get('.positive-feedback-on').should('have.length', 1);
}

function threadQueue() {
  cy.get('.step').eq(1).should('contain', 'Create step counter: 0');
  cy.get('.step').eq(3).should('contain', 'Create step counter: 5');
  cy.get('.step').eq(6).should('contain', 'Create step counter: 8');
}

function threadList() {
  cy.get('#thread-test1').should('contain', 'thread 1');
  cy.get('#thread-test2').should('contain', 'thread 2');

  // Test thread page
  cy.get('#thread-test1').click();
  cy.get('.step').should('have.length', 2);
  cy.get('.step').eq(0).should('contain', 'Message 1');
  cy.get('.step').eq(1).should('contain', 'Message 2');

  // Test thread delete
  cy.get('#thread-test1').find('#thread-options').click();
  cy.wait(100);
  cy.get('#delete-thread').click();
  cy.wait(100);
  cy.get("[role='alertdialog'] button.bg-primary").click();
  cy.wait(100);
  cy.get('#thread-test1').should('not.exist');
  // Close the thread options popover
  cy.get('body').type('{esc}');
}

function resumeThread() {
  // Go to the "thread 2" thread and resume it
  cy.get('#thread-test2').click();
  cy.wait(1000);
  // back to the "hello" thread
  cy.get('a').contains('Hello').click();
  cy.wait(1000);

  cy.get('.step').should('have.length', 10);

  cy.get('.step').eq(0).should('contain', 'Hello');
  cy.get('.step').eq(7).should('contain', 'Welcome back to Hello');
  cy.get('.step').eq(8).should('contain', 'chat_profile');
}

function restartServer(
  mode: ExecutionMode = undefined,
  env?: Record<string, string>
) {
  const pathItems = Cypress.spec.absolute.split(sep);
  const testName = pathItems[pathItems.length - 2];
  cy.exec(`pnpm exec ts-node ./cypress/support/run.ts ${testName} ${mode}`, {
    env
  });
}

function continueThread() {
  cy.get('.step').eq(7).should('contain', 'Welcome back to Hello');

  submitMessage('Hello after restart');

  // Verify that new step counter messages have been added
  cy.get('.step').eq(11).should('contain', 'Create step counter: 14');
  cy.get('.step').eq(14).should('contain', 'Create step counter: 17');
}

function newThread() {
  cy.get('#new-chat-button').click();
  cy.get('#confirm').click();
}

describe('Data Layer', () => {
  beforeEach(() => {
    // Set up the thread history file
    const pathItems = Cypress.spec.absolute.split(sep);
    pathItems[pathItems.length - 1] = 'thread_history.pickle';
    const threadHistoryFile = pathItems.join(sep);
    cy.wrap(threadHistoryFile).as('threadHistoryFile');

    runTestServer(undefined, {
      THREAD_HISTORY_PICKLE_PATH: threadHistoryFile
    });
  });

  afterEach(() => {
    cy.get('@threadHistoryFile').then((threadHistoryFile) => {
      // Clean up the thread history file
      cy.exec(`rm -f ${threadHistoryFile}`);
    });
  });

  describe('Data Features with persistence', () => {
    it('should login, submit feedback, wait for user input to create steps, browse thread history, delete a thread and then resume a thread', () => {
      login();
      cy.wait(1000);
      feedback();
      threadQueue();
      threadList();
      resumeThread();
    });

    it('should continue the thread after backend restarts and work with new thread as usual', () => {
      login();
      cy.wait(1000);
      feedback();
      threadQueue();

      cy.get('@threadHistoryFile').then((threadHistoryFile) => {
        restartServer(undefined, {
          THREAD_HISTORY_PICKLE_PATH: `${threadHistoryFile}`
        });
      });
      // Continue the thread and verify that the step counter is not reset
      continueThread();

      // Create a new thread and verify that the step counter is reset
      newThread();
      cy.wait(1000);
      feedback();
      threadQueue();
    });
  });
});
