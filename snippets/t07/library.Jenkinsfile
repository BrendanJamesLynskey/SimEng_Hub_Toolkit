// Using the shared library, plus a credential that never appears in the log.
@Library('simeng-ci') _

node('sim') {
    git url: 'https://github.com/BrendanJamesLynskey/Memory_System_Sim.git', branch: 'main'
    simRegression(gate: 'ci/perf_gate.py --margin 0.5', results: 'examples/results.py',
                  resultsFile: 'examples/results.md')
    stage('Publish (credential demo)') {
        withCredentials([string(credentialsId: 'results-upload-token', variable: 'TOKEN')]) {
            // The token is masked wherever it would be printed.
            sh 'echo "would upload results.md with token $TOKEN"'
        }
    }
}
