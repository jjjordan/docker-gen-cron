#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

const char *python3 = "/usr/bin/python3";
const char *runjob = "/opt/lib/runjob.py";

extern char **environ;

int main(int argc, char **argv)
{
	const char **pyargv, **pyenv;
	int elen;
	int i, t;

	/* Count environment */
	for (elen = 0; environ[elen]; elen++) { }

	/* Copy and filter environment */
	pyenv = (const char **) malloc((elen + 1) * sizeof(char *));
	for (i = 0, t = 0; i < elen; i++) {
		if (strncmp("PYTHON", environ[i], 6)) {
			pyenv[t++] = environ[i];
		}
	}

	pyenv[t] = NULL;

	/* Copy and modify argv */
	t = 0;
	pyargv = (const char **) malloc((argc + 1) * sizeof(char *));
	pyargv[t++] = python3;
	pyargv[t++] = runjob;
	for (i = 1; i < argc; i++) {
		pyargv[t++] = argv[i];
	}

	pyargv[t] = NULL;

	/* Exec in */
	execve(python3, (char *const *)pyargv, (char *const *)pyenv);

	/* Why are we still here? */
	perror("execve");
	return 1;
}
