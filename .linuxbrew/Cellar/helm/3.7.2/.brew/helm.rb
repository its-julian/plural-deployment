class Helm < Formula
  desc "Kubernetes package manager"
  homepage "https://helm.sh/"
  url "https://github.com/helm/helm.git",
      tag:      "v3.7.2",
      revision: "663a896f4a815053445eec4153677ddc24a0a361"
  license "Apache-2.0"
  head "https://github.com/helm/helm.git", branch: "main"

  depends_on "go" => :build

  def install
    # Don't dirty the git tree
    rm_rf ".brew_home"

    system "make", "build"
    bin.install "bin/helm"

    mkdir "man1" do
      system bin/"helm", "docs", "--type", "man"
      man1.install Dir["*"]
    end

    output = Utils.safe_popen_read(bin/"helm", "completion", "bash")
    (bash_completion/"helm").write output

    output = Utils.safe_popen_read(bin/"helm", "completion", "zsh")
    (zsh_completion/"_helm").write output

    output = Utils.safe_popen_read(bin/"helm", "completion", "fish")
    (fish_completion/"helm.fish").write output
  end

  test do
    system bin/"helm", "create", "foo"
    assert File.directory? testpath/"foo/charts"

    version_output = shell_output(bin/"helm version 2>&1")
    assert_match "GitTreeState:\"clean\"", version_output
    if build.stable?
      revision = stable.instance_variable_get(:@resource).instance_variable_get(:@specs)[:revision]
      assert_match "GitCommit:\"#{revision}\"", version_output
      assert_match "Version:\"v#{version}\"", version_output
    end
  end
end
