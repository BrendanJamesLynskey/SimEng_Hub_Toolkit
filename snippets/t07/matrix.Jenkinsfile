// A parameter sweep as a declarative matrix: every preset x pattern cell runs in
// parallel, on any agent with the label 'sim' (here, the built-in node).
pipeline {
    agent none
    options { timeout(time: 20, unit: 'MINUTES') }
    stages {
        stage('Checkout once') {
            agent { label 'sim' }
            steps {
                git url: 'https://github.com/BrendanJamesLynskey/Memory_System_Sim.git', branch: 'main'
                stash name: 'src', includes: 'src/**'
            }
        }
        stage('Sweep') {
            matrix {
                agent { label 'sim' }
                axes {
                    axis { name 'PRESET';  values 'ddr4', 'hbm' }
                    axis { name 'PATTERN'; values 'stream', 'random', 'stride' }
                }
                excludes {
                    exclude {                       // not a meaningful cell for this demo
                        axis { name 'PRESET';  values 'hbm' }
                        axis { name 'PATTERN'; values 'stride' }
                    }
                }
                stages {
                    stage('Simulate') {
                        steps {
                            unstash 'src'
                            sh 'PYTHONPATH=src python3 -m memsim.cli --preset $PRESET --pattern $PATTERN --n 3000 | tee cell.txt'
                            sh 'mv cell.txt "cell-$PRESET-$PATTERN.txt"'
                            archiveArtifacts artifacts: "cell-${PRESET}-${PATTERN}.txt"
                        }
                    }
                }
            }
        }
    }
}
