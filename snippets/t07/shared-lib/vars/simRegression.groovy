// A shared-library step: one call gives any simulator repo the house regression
// stages (setup, tests with JUnit, gate, results). Lives in its own Git repo and is
// loaded with @Library('simeng-ci').
def call(Map cfg) {
    String py = cfg.get('python', 'python3')
    stage('Setup') {
        sh "${py} -m venv .venv && .venv/bin/pip install -q -e '.[test]'"
    }
    stage('Tests') {
        sh ".venv/bin/pytest -p no:logging --junitxml=junit.xml ${cfg.get('pytestArgs', '')}"
        junit 'junit.xml'
    }
    if (cfg.gate) {
        stage('Gate') {
            sh ".venv/bin/python ${cfg.gate}"
        }
    }
    if (cfg.results) {
        stage('Results') {
            sh ".venv/bin/python ${cfg.results} > /dev/null"
            archiveArtifacts artifacts: cfg.resultsFile
        }
    }
}
