// The same sweep as a scripted pipeline: plain Groovy, so loops, maps and
// try/catch are available; parallel branches are built as a map.
node('sim') {
    stage('Checkout') {
        git url: 'https://github.com/BrendanJamesLynskey/Memory_System_Sim.git', branch: 'main'
    }
    stage('Sweep') {
        def cells = [:]
        for (preset in ['ddr4', 'hbm']) {
            for (pattern in ['stream', 'random']) {
                def p = preset, q = pattern            // capture loop variables for the closure
                cells["${p}/${q}"] = {
                    sh "PYTHONPATH=src python3 -m memsim.cli --preset ${p} --pattern ${q} --n 3000"
                }
            }
        }
        parallel cells
    }
    stage('A failure that is handled') {
        try {
            sh 'PYTHONPATH=src python3 -m memsim.cli --preset no-such-preset'
        } catch (err) {
            echo "expected failure, handled: ${err}"
            currentBuild.description = 'sweep ok; bad preset rejected'
        }
    }
}
