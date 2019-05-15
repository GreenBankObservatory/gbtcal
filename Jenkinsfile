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

    stage('python{2,3}') {
      parallel {
        stage('python2') {
          agent {
            label 'rhel7'
          }
          stages {
            stage('python2.virtualenv') {
              steps {
                sh """./createEnv ${venv_name}"""
              }
            }

            stage('python2.test') {
              steps {
                sh """
                  source ${venv_name}/bin/activate
                  nosetests --with-xunit
                """
                junit '*.xml'
              }
            }

            stage('python2.package') {
              steps {
                sh """
                  source ${venv_name}/bin/activate
                  pip install wheel
                  python setup.py sdist
                  python setup.py bdist_wheel
                """
              }
            }
          }
        }

        stage('python3') {
          agent {
            label 'rhel7'
          }
          stages {
            stage('python3.virtualenv') {
              steps {
                sh """python3 -m venv ${venv_name}
                source ${venv_name}/bin/activate
                pip install -r requirements.txt -r requirements-test.txt"""
              }
            }

            stage('python3.test') {
              steps {
                sh """
                  source ${venv_name}/bin/activate
                  nosetests --with-xunit
                """
                junit '*.xml'
              }
            }

            stage('python3.package') {
              steps {
                sh """
                  source ${venv_name}/bin/activate
                  pip install wheel
                  python setup.py sdist
                  python setup.py bdist_wheel
                """
              }
            }
          }
        }
      }
    }
  }

  post {
    regression {
        script { env.CHANGED = true }
    }

    fixed {
        script { env.CHANGED = true }
    }

    cleanup {
        do_notify()
    }
  }
}
