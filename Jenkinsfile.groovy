
node {
    stage('cleanup') {
        deleteDir()
    }

    stage('checkout') {
        checkout scm
    }
}    
