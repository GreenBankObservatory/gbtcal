// This is the name given to the virtual environment for
// this build
def venv_name = "testing-gbtcal-env"

pipeline {
  agent any

  stages {
    stage('init') {
      steps {
        lastChanges(
          since: 'LAST_SUCCESSFUL_BUILD',
          format:'SIDE',
          matching: 'LINE'
        )
      }
    }

    stage('install') {
      steps {
        sh """./createEnv "${venv_name}" """
      }
    }

    stage('test') {
      steps {
        sh """
          source ./${venv_name}/bin/activate
          nosetests --with-xunit
        """
        junit '*.xml'
      }
    }
  }

  post {
    always {
      do_notify()
    }
  }
}
