def lastCommit() {
    sh 'git log --format="%ae" | head -1 > commit-author.txt'                 
    lastAuthor = readFile('commit-author.txt').trim()
    sh 'rm commit-author.txt'
    return lastAuthor
}

// Used to send email notification of success or failure
def notify(status, details){
    def failure_description = "";
    def lastChangedBy = lastCommit()
    if (status == 'failure') {
        failure_description = """${env.BUILD_NUMBER} failed."""
    }
    emailext (
      to: "sddev@nrao.edu",
      subject: "${status}: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]'",
      body: """${status}: Job '${env.JOB_NAME} [${env.BUILD_NUMBER}]':
        ${failure_description}
        Last commit by: ${lastChangedBy}
        Build summary: ${env.BUILD_URL}"""
    )
}

// This is the name given to the virtual environment for
// this build
venv_name = "testing-gbtcal-env"

def installPythonPackages() {
    sh """
    virtualenv -p /opt/local/bin/python2.7 ${venv_name}
    source ${venv_name}/bin/activate
    pip install -U pip setuptools
    pip install -r requirements.txt"""
}

def testPython() {
    sh """source ./${venv_name}/bin/activate
    cd gbtcal/test
    nosetests --with-xunit --nocapture test_calibrator.py"""
}

node {
    withEnv(['PATH=/opt/local/bin:$PATH']) {
        stage('cleanup') {
            deleteDir()
        }
    
        stage('checkout') {
            checkout scm
        }
    
        stage('install') {
            try {
                installPythonPackages()
            } catch(error) {
                notify('failure', 'An error has occurred during the <b>install</b> stage.')
                throw(error)
            }
        }
    
        stage('test') {
            try {
                testPython()
                junit 'gbtcal/test/*.xml'
            } catch(error) {
                notify('failure', 'An error has occurred during the <b>test</b> stage.')
                throw(error)
            }
        }
    
        stage('notify') {
            notify('success', 'gbtcal system built and tested successfully.')
        }
    }    
}
