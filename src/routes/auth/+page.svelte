<script>
	import { toast } from 'svelte-sonner';

	import { onMount, getContext, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { getBackendConfig } from '$lib/apis';
	import { ldapUserSignIn, getSessionUser, userSignIn, userSignUp } from '$lib/apis/auths';

	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';
	import { WEBUI_NAME, config, user, socket } from '$lib/stores';

	import { generateInitialsImage, canvasPixelTest } from '$lib/utils';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import OnBoarding from '$lib/components/OnBoarding.svelte';
	

	const i18n = getContext('i18n');

	let loaded = false;
	let showInitialLoading = true;
	let loadingStepMessage = '';

	/* ---------- ①  图形验证码 & 邮箱验证码  ---------- */
	let captchaToken = '';
	let captchaImg   = '';
	let captchaInput = '';
	let emailCode    = '';
	let showCaptchaInput = false;
	
	async function loadCaptcha() {
	    const r = await fetch(`${WEBUI_API_BASE_URL}/auths/captcha`);
	    if (r.ok) {
	        const { token, image } = await r.json();
	        captchaToken = token;
	        captchaImg   = image;
	        captchaInput = '';
	    }
	}
	
	async function checkIfEmailNeedsCaptcha(currentEmail) {
		if (!currentEmail) return false;
		try {
			const res = await fetch(`${WEBUI_API_BASE_URL}/auths/check_email_captcha`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email: currentEmail })
			});
			if (res.ok) {
				const data = await res.json();
				return data.needs_captcha;
			}
			return false;
		} catch (e) {
			console.error('Error checking if email needs captcha:', e);
			return false;
		}
	}
	
	async function sendEmailCode() {
		if (!email) {
			toast.error('请填写邮箱');
			return;
		}

		const needsCaptcha = await checkIfEmailNeedsCaptcha(email);
		showCaptchaInput = needsCaptcha;

		if (needsCaptcha && !captchaInput) {
			toast.error('请填写图形验证码');
			if (!captchaToken) loadCaptcha();
			return;
		}

		const body = {
			email,
			...(needsCaptcha && { captcha_token: captchaToken, captcha_code: captchaInput })
		};

		try {
			const r = await fetch(`${WEBUI_API_BASE_URL}/auths/send_email_code`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});

			const responseData = await r.json().catch(() => null);

			if (!r.ok) {
				if (responseData?.detail === 'Captcha invalid') {
					toast.error('图形验证码错误或已过期');
					loadCaptcha();
				} else if (responseData?.detail === 'Captcha required') {
					toast.error('操作频繁，请输入图形验证码');
					showCaptchaInput = true;
					if (!captchaToken) loadCaptcha();
				} else {
					toast.error(responseData?.detail || '发送失败，请检查邮箱');
				}
			} else {
				toast.success('验证码已发送，请查收邮件');
				if (responseData?.needs_captcha) {
					showCaptchaInput = true;
					loadCaptcha();
				} else {
					showCaptchaInput = false;
				}
			}
		} catch (e) {
			console.error('Error sending email code:', e);
			toast.error('发送邮件验证码时出错');
		}
	}
	/* ------------------------------------------------- */
	let mode = $config?.features.enable_ldap ? 'ldap' : 'signin';

	let name = '';
	let email = '';
	let password = '';
	let newPassword = '';

	let ldapUsername = '';

	const querystringValue = (key) => {
		const querystring = window.location.search;
		const urlParams = new URLSearchParams(querystring);
		return urlParams.get(key);
	};

	const setSessionUser = async (sessionUser) => {
		if (sessionUser) {
			console.log(sessionUser);
			toast.success($i18n.t(`You're now logged in.`));
			if (sessionUser.token) {
				localStorage.token = sessionUser.token;
			}

			$socket.emit('user-join', { auth: { token: sessionUser.token } });
			await user.set(sessionUser);
			await config.set(await getBackendConfig());

			const redirectPath = querystringValue('redirect') || '/';
			goto(redirectPath);
		}
	};

	const signInHandler = async () => {
		const sessionUser = await userSignIn(email, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		await setSessionUser(sessionUser);
	};

	const signUpHandler = async () => {
		if (!name || !email || !password || !emailCode) {
			toast.error('请填写所有必填项');
			return;
		}
		const sessionUser = await userSignUp(
			name,
			email,
			password,
			generateInitialsImage(name),
			emailCode
		).catch((error) => {
			toast.error(`${error}`);
			if (error.message.includes('Invalid email code')) {
				// 邮箱验证码错误，不清空图形验证码
			} else {
				loadCaptcha();
			}
			return null;
		});

		await setSessionUser(sessionUser);
	};

	const ldapSignInHandler = async () => {
		const sessionUser = await ldapUserSignIn(ldapUsername, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		await setSessionUser(sessionUser);
	};

	const resetPasswordHandler = async () => {
		if (!email || !emailCode || !newPassword) {
			toast.error('请填写邮箱、邮箱验证码和新密码');
			return;
		}
		try {
			const res = await fetch(`${WEBUI_API_BASE_URL}/auths/reset_password`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email, email_code: emailCode, new_password: newPassword })
			});
			const data = await res.json();
			if (res.ok && data.success) {
				toast.success('密码重置成功，请使用新密码登录');
				mode = 'signin';
				password = '';
				emailCode = '';
				newPassword = '';
				showCaptchaInput = false;
			} else {
				toast.error(data.detail || '密码重置失败');
				if (data.detail === 'Invalid email code') {
					// 邮箱验证码错误
				} else {
					loadCaptcha();
				}
			}
		} catch (error) {
			toast.error('密码重置请求失败');
			console.error('Error resetting password:', error);
			loadCaptcha();
		}
	};

	const submitHandler = async () => {
		if (mode === 'ldap') {
			await ldapSignInHandler();
		} else if (mode === 'signin') {
			await signInHandler();
		} else if (mode === 'signup') {
			await signUpHandler();
		} else if (mode === 'reset_password') {
			await resetPasswordHandler();
		}
	};

	const checkOauthCallback = async () => {
		if (!$page.url.hash) {
			return;
		}
		const hash = $page.url.hash.substring(1);
		if (!hash) {
			return;
		}
		const params = new URLSearchParams(hash);
		const token = params.get('token');
		if (!token) {
			return;
		}
		const sessionUser = await getSessionUser(token).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		if (!sessionUser) {
			return;
		}
		localStorage.token = token;
		await setSessionUser(sessionUser);
	};

	let onboarding = false;

	async function setLogoImage() {
		await tick();
		const logo = document.getElementById('logo');

		if (logo) {
			const isDarkMode = document.documentElement.classList.contains('dark');

			if (isDarkMode) {
				const darkImage = new Image();
				darkImage.src = '/static/favicon-dark.png';

				darkImage.onload = () => {
					logo.src = '/static/favicon-dark.png';
					logo.style.filter = ''; // Ensure no inversion is applied if favicon-dark.png exists
				};

				darkImage.onerror = () => {
					logo.style.filter = 'invert(1)'; // Invert image if favicon-dark.png is missing
				};
			}
		}
	}

	onMount(async () => {
		loadingStepMessage = $i18n.t('Initializing session...');
		if ($user !== undefined) {
			const redirectPath = querystringValue('redirect') || '/';
			goto(redirectPath);
			return;
		}

		loadingStepMessage = $i18n.t('Checking authentication status...');
		await checkOauthCallback();

		// It's important to get the config first to check features.
		loadingStepMessage = $i18n.t('Loading backend configuration...');
		try {
			const backendConfig = await getBackendConfig();
			config.set(backendConfig); // Set config early

			if ((backendConfig?.features.auth_trusted_header ?? false) || backendConfig?.features.auth === false) {
				loadingStepMessage = $i18n.t('Attempting auto sign-in...');
				await signInHandler(); // signInHandler might navigate away if successful
				if ($user) return; // If signInHandler was successful and set user, stop here
			} else {
				onboarding = backendConfig?.onboarding ?? false;
			}
		} catch (error) {
			console.error("Failed to load backend configuration:", error);
			toast.error($i18n.t('Failed to load backend configuration. Please try again later.'));
			// Potentially set loaded to true here to show an error message on the page
			// instead of being stuck on loading. Or provide a retry mechanism.
			loaded = true; // Or handle error appropriately
			showInitialLoading = false; // Hide loading, show error or retry
			return;
		}
		
		loadingStepMessage = $i18n.t('Finalizing setup...');
		loaded = true;
		showInitialLoading = false;
		setLogoImage();
	});

	$: if (mode) {
		password = '';
		if (mode !== 'reset_password') {
			newPassword = '';
		}
		if (mode === 'signup' || mode === 'reset_password') {
			// 注册和重置密码模式下，如果邮箱变了，需要重新判断是否需要图形验证码
			// checkIfEmailNeedsCaptcha(email).then(needs => showCaptchaInput = needs);
			// 或者更简单地，在sendEmailCode函数内部处理
		} else {
			showCaptchaInput = false;
		}
	}
</script>

<svelte:head>
	<title>
		{`${$WEBUI_NAME}`}
	</title>
</svelte:head>

{#if showInitialLoading}
	<div class="fixed inset-0 flex items-center justify-center bg-white dark:bg-black z-[100]">
		<Spinner size="xl" /> <span class="ml-3 text-lg dark:text-white">{loadingStepMessage || $i18n.t('Loading...')}</span>
	</div>
{/if}

<OnBoarding
	bind:show={onboarding}
	getStartedHandler={() => {
		onboarding = false;
		mode = $config?.features.enable_ldap ? 'ldap' : 'signup';
	}}
/>

<div class="w-full min-h-screen max-h-[100dvh] text-gray-800 dark:text-white relative bg-gradient-to-br from-purple-50 via-pink-50 to-blue-50 dark:from-gray-800 dark:via-gray-900 dark:to-black">
	<div class="w-full absolute top-0 left-0 right-0 h-8 drag-region" />

	{#if loaded}
		<div class="fixed m-6 md:m-10 z-50">
			<div class="flex space-x-2 items-center">
				<img
					id="logo"
					crossorigin="anonymous"
					src="{WEBUI_BASE_URL}/static/splash.png"
					class="w-8 h-8 md:w-10 md:h-10 rounded-full shadow-md"
					alt="logo"
				/>
				<span class="text-lg md:text-xl font-semibold text-gray-700 dark:text-gray-200">{$WEBUI_NAME}</span>
			</div>
		</div>

		<div
			class="min-h-screen w-full flex items-center justify-center p-4 font-primary z-40"
		>
			<div class="w-full max-w-md bg-white dark:bg-gray-800 shadow-2xl rounded-xl p-6 md:p-10 transform transition-all duration-500 ease-in-out">
				{#if ($config?.features.auth_trusted_header ?? false) || $config?.features.auth === false}
					<div class=" my-auto py-10 w-full text-center">
						<div
							class="flex items-center justify-center gap-3 text-xl sm:text-2xl font-semibold text-gray-700 dark:text-gray-200"
						>
							<Spinner />
							<span>
								{$i18n.t('Signing in to {{WEBUI_NAME}}', { WEBUI_NAME: $WEBUI_NAME })}
							</span>
						</div>
					</div>
				{:else}
					<div class="w-full text-gray-700 dark:text-gray-100">
						<form
							class="flex flex-col justify-center space-y-6"
							on:submit|preventDefault={submitHandler}
						>
							<div class="text-center">
								<h1 class="text-2xl sm:text-3xl font-bold mb-2">
									{#if $config?.onboarding ?? false}
										{$i18n.t(`Get started with {{WEBUI_NAME}}`, { WEBUI_NAME: $WEBUI_NAME })}
									{:else if mode === 'ldap'}
										{$i18n.t(`Sign in with LDAP`)}
									{:else if mode === 'signin'}
										{$i18n.t(`Welcome Back!`)}
									{:else if mode === 'signup'}
										{$i18n.t(`Create Your Account`)}
									{:else if mode === 'reset_password'}
										{$i18n.t(`Reset Your Password`)}
									{/if}
								</h1>
								{#if !($config?.onboarding ?? false) && mode === 'signin'}
									<p class="text-sm text-gray-500 dark:text-gray-400">{$i18n.t('Sign in to continue to {{WEBUI_NAME}}.', {WEBUI_NAME: $WEBUI_NAME})}</p>
								{:else if !($config?.onboarding ?? false) && mode === 'signup'}
									<p class="text-sm text-gray-500 dark:text-gray-400">{$i18n.t('Join us and start exploring.')}</p>
								{:else if mode === 'reset_password'}
									<p class="text-sm text-gray-500 dark:text-gray-400">{$i18n.t('Enter your email to reset your password.')}</p>
								{/if}

								{#if $config?.onboarding ?? false}
									<p class="mt-2 text-xs font-medium text-gray-500 dark:text-gray-400">
										ⓘ {$WEBUI_NAME}
										{$i18n.t(
											'does not make any external connections, and your data stays securely on your locally hosted server.'
										)}
									</p>
								{/if}
							</div>

							{#if $config?.features.enable_login_form || $config?.features.enable_ldap || mode === 'reset_password'}
								<div class="flex flex-col space-y-4">
									{#if mode === 'signup'}
										<div>
											<label for="name" class="block text-sm font-medium text-left mb-1">{$i18n.t('Name')}</label>
											<input
												id="name"
												bind:value={name}
												type="text"
												class="input"
												autocomplete="name"
												placeholder={$i18n.t('Enter Your Full Name')}
												required
											/>
										</div>
									{/if}

									{#if mode === 'ldap'}
										<div>
											<label for="ldapUsername" class="block text-sm font-medium text-left mb-1">{$i18n.t('Username')}</label>
											<input
												id="ldapUsername"
												bind:value={ldapUsername}
												type="text"
												class="input"
												autocomplete="username"
												name="username"
												placeholder={$i18n.t('Enter Your Username')}
												required
											/>
										</div>
									{:else}
										<div>
											<label for="email" class="block text-sm font-medium text-left mb-1">{$i18n.t('Email')}</label>
											<input
												id="email"
												bind:value={email}
												type="email"
												class="input"
												autocomplete="email"
												name="email"
												placeholder={$i18n.t('Enter Your Email')}
												required
												on:blur={() => {
													if (mode === 'signup' || mode === 'reset_password') {
														checkIfEmailNeedsCaptcha(email).then(needs => {
															showCaptchaInput = needs;
															if (needs && !captchaToken) loadCaptcha();
														});
													}
												}}
											/>
										</div>
									{/if}

									{#if (mode === 'signup' || mode === 'reset_password') && showCaptchaInput}
										<div class="flex items-end space-x-2">
											<div class="flex-grow">
												<label for="captchaInput" class="block text-sm font-medium text-left mb-1">{$i18n.t('Captcha')}</label>
												<input
													id="captchaInput"
													bind:value={captchaInput}
													type="text"
													class="input"
													placeholder={$i18n.t('Enter Captcha')}
													required={showCaptchaInput}
												/>
											</div>
											<img
												src={captchaImg}
												alt="captcha"
												class="h-10 border border-gray-300 dark:border-gray-600 rounded-md cursor-pointer object-cover"
												title={$i18n.t('Click to refresh captcha')}
												on:click={loadCaptcha}
											/>
										</div>
									{/if}

									{#if mode === 'signup' || mode === 'reset_password'}
										<div class="flex items-end space-x-2">
											<div class="flex-grow">
												<label for="emailCode" class="block text-sm font-medium text-left mb-1">{$i18n.t('Email Code')}</label>
												<input
													id="emailCode"
													bind:value={emailCode}
													type="text"
													class="input"
													placeholder={$i18n.t('Enter Email Code')}
													required
												/>
											</div>
											<button
												class="btn btn-secondary h-10 flex-shrink-0 px-4"
												type="button"
												on:click={sendEmailCode}
											>
												{$i18n.t('Send')}
											</button>
										</div>
									{/if}

									{#if mode !== 'reset_password'}
										<div>
											<div class="flex justify-between items-center mb-1">
												<label for="password" class="block text-sm font-medium text-left">{$i18n.t('Password')}</label>
												{#if mode === 'signin'}
													<button
														type="button"
														class="text-xs font-medium text-purple-600 hover:text-purple-500 dark:text-purple-400 dark:hover:text-purple-300"
														on:click={() => {
															mode = 'reset_password';
															if(email) checkIfEmailNeedsCaptcha(email).then(needs => showCaptchaInput = needs);
														}}
													>
														{$i18n.t('Forgot Password?')}
													</button>
												{/if}
											</div>
											<input
												id="password"
												bind:value={password}
												type="password"
												class="input"
												placeholder={$i18n.t('Enter Your Password')}
												autocomplete={mode === 'signin' ? "current-password" : "new-password"}
												name={mode === 'signin' ? "current-password" : "new-password"}
												required
											/>
										</div>
									{/if}

									{#if mode === 'reset_password'}
										<div>
											<label for="newPassword" class="block text-sm font-medium text-left mb-1">{$i18n.t('New Password')}</label>
											<input
												id="newPassword"
												bind:value={newPassword}
												type="password"
												class="input"
												placeholder={$i18n.t('Enter Your New Password')}
												autocomplete="new-password"
												required
											/>
										</div>
									{/if}
								</div>
							{/if}

							<div class="mt-6">
								{#if $config?.features.enable_login_form || $config?.features.enable_ldap || mode === 'reset_password'}
									{#if mode === 'ldap'}
										<button class="btn btn-primary w-full" type="submit">
											{$i18n.t('Authenticate')}
										</button>
									{:else if mode === 'reset_password'}
										<button class="btn btn-primary w-full" type="submit">
											{$i18n.t('Reset Password')}
										</button>
									{:else}
										<button class="btn btn-primary w-full" type="submit">
											{mode === 'signin'
												? $i18n.t('Sign in')
												: ($config?.onboarding ?? false)
													? $i18n.t('Create Admin Account')
													: $i18n.t('Create Account')}
										</button>
									{/if}

									{#if !($config?.onboarding ?? false) && (mode === 'signin' || mode === 'signup')}
										<div class="mt-4 text-sm text-center text-gray-600 dark:text-gray-400">
											{mode === 'signin'
												? $i18n.t("Don't have an account?")
												: $i18n.t('Already have an account?')}

											<button
												class="ml-1 font-medium text-purple-600 hover:text-purple-500 dark:text-purple-400 dark:hover:text-purple-300 underline"
												type="button"
												on:click={() => {
													if (mode === 'signin') {
														mode = 'signup';
														if(email) checkIfEmailNeedsCaptcha(email).then(needs => {
															showCaptchaInput = needs;
															if (needs && !captchaToken) loadCaptcha();
														});
													} else {
														mode = 'signin';
														showCaptchaInput = false;
													}
												}}
											>
												{mode === 'signin' ? $i18n.t('Sign up') : $i18n.t('Sign in')}
											</button>
										</div>
									{/if}
									{#if mode === 'reset_password'}
										<div class="mt-4 text-sm text-center">
											<button
												class="font-medium text-purple-600 hover:text-purple-500 dark:text-purple-400 dark:hover:text-purple-300 underline"
												type="button"
												on:click={() => {
													mode = 'signin';
													showCaptchaInput = false;
												}}
											>
												{$i18n.t('Back to Sign In')}
											</button>
										</div>
									{/if}
								{/if}
							</div>
						</form>

						{#if Object.keys($config?.oauth?.providers ?? {}).length > 0 && (mode === 'signin' || mode === 'signup')}
							<div class="inline-flex items-center justify-center w-full my-6">
								<hr class="w-full h-px border-0 bg-gray-200 dark:bg-gray-700" />
								{#if $config?.features.enable_login_form || $config?.features.enable_ldap}
									<span
										class="absolute px-3 text-sm font-medium text-gray-500 dark:text-gray-400 -translate-x-1/2 bg-white dark:bg-gray-800 left-1/2"
										>{$i18n.t('or continue with')}</span
									>
								{/if}
							</div>
							<div class="flex flex-col space-y-3">
								{#if $config?.oauth?.providers?.google}
									<button
										class="btn btn-outline w-full flex justify-center items-center"
										on:click={() => {
											window.location.href = `${WEBUI_BASE_URL}/oauth/google/login`;
										}}
									>
										<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" class="size-5 mr-2">
											<path
												fill="#EA4335"
												d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
											/><path
												fill="#4285F4"
												d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
											/><path
												fill="#FBBC05"
												d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
											/><path
												fill="#34A853"
												d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
											/><path fill="none" d="M0 0h48v48H0z" />
										</svg>
										<span>{$i18n.t('{{provider}}', { provider: 'Google' })}</span>
									</button>
								{/if}
								{#if $config?.oauth?.providers?.microsoft}
									<button
										class="btn btn-outline w-full flex justify-center items-center"
										on:click={() => {
											window.location.href = `${WEBUI_BASE_URL}/oauth/microsoft/login`;
										}}
									>
										<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 21 21" class="size-5 mr-2">
											<rect x="1" y="1" width="9" height="9" fill="#f25022" /><rect
												x="1"
												y="11"
												width="9"
												height="9"
												fill="#00a4ef"
											/><rect x="11" y="1" width="9" height="9" fill="#7fba00" /><rect
												x="11"
												y="11"
												width="9"
												height="9"
												fill="#ffb900"
											/>
										</svg>
										<span>{$i18n.t('{{provider}}', { provider: 'Microsoft' })}</span>
									</button>
								{/if}
								{#if $config?.oauth?.providers?.github}
									<button
										class="btn btn-outline w-full flex justify-center items-center"
										on:click={() => {
											window.location.href = `${WEBUI_BASE_URL}/oauth/github/login`;
										}}
									>
										<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" class="size-5 mr-2 fill-current">
											<path
												d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.92 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57C20.565 21.795 24 17.31 24 12c0-6.63-5.37-12-12-12z"
											/>
										</svg>
										<span>{$i18n.t('{{provider}}', { provider: 'GitHub' })}</span>
									</button>
								{/if}
								{#if $config?.oauth?.providers?.oidc}
									<button
										class="btn btn-outline w-full flex justify-center items-center"
										on:click={() => {
											window.location.href = `${WEBUI_BASE_URL}/oauth/oidc/login`;
										}}
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											fill="none"
											viewBox="0 0 24 24"
											stroke-width="1.5"
											stroke="currentColor"
											class="size-5 mr-2"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												d="M15.75 5.25a3 3 0 0 1 3 3m3 0a6 6 0 0 1-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1 1 21.75 8.25Z"
											/>
										</svg>

										<span
											>{$i18n.t('{{provider}}', {
												provider: $config?.oauth?.providers?.oidc ?? 'SSO'
											})}</span
										>
									</button>
								{/if}
							</div>
						{/if}

						{#if $config?.features.enable_ldap && $config?.features.enable_login_form && (mode === 'signin' || mode === 'ldap')}
							<div class="mt-6 text-center">
								<button
									class="text-sm font-medium text-purple-600 hover:text-purple-500 dark:text-purple-400 dark:hover:text-purple-300 underline"
									type="button"
									on:click={() => {
										if (mode === 'ldap')
											mode = ($config?.onboarding ?? false) ? 'signup' : 'signin';
										else mode = 'ldap';
										showCaptchaInput = false;
									}}
								>
									<span
										>{mode === 'ldap'
											? $i18n.t('Continue with Email')
											: $i18n.t('Continue with LDAP')}</span
									>
								</button>
							</div>
						{/if}
					</div>
				{/if}
			</div>
		</div>
	{/if}
</div>

<style lang="postcss">
	.input {
		@apply w-full px-4 py-2.5 text-sm border border-gray-300 rounded-lg shadow-sm bg-gray-50 dark:bg-gray-700 dark:border-gray-600 dark:text-white focus:ring-purple-500 focus:border-purple-500 dark:focus:ring-purple-500 dark:focus:border-purple-500 transition-colors duration-200;
	}
	.btn {
		@apply py-2.5 px-5 text-sm font-medium rounded-lg transition-all duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-offset-2 dark:focus:ring-offset-gray-800;
	}
	.btn-primary {
		@apply text-white bg-purple-600 hover:bg-purple-700 focus:ring-purple-500;
	}
	.btn-secondary {
		@apply text-purple-700 bg-purple-100 hover:bg-purple-200 dark:text-purple-300 dark:bg-purple-700 dark:hover:bg-purple-600 focus:ring-purple-500;
	}
	.btn-outline {
		@apply text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 dark:text-gray-300 dark:bg-gray-700 dark:border-gray-600 dark:hover:bg-gray-600 focus:ring-gray-300 dark:focus:ring-gray-500;
	}
</style>
