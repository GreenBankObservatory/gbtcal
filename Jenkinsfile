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

    stage('virtualenv') {
      steps {
        sh """./createEnv ${venv_name}"""
      }
    }

    stage('test') {
      steps {
        sh """
          source ${venv_name}/bin/activate
          nosetests --with-xunit
        """
        junit '*.xml'
      }
    }

    stage('package') {
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
